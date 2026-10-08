"""
SAT-SA Ingestion Service
Handles multi-format file ingestion (CSV, JSON), streaming/chunked parsing,
duplicate detection, quality profiling, and atomic database persistence.
"""

import io
import json
import csv
import uuid
import datetime
import hashlib
from typing import Dict, Any, List, Tuple, Optional
from sqlalchemy.orm import Session

from app.models import domain
from app.services.adapters import detect_dataset_type, map_columns_to_canonical
from app.services.validation import (
    validate_and_normalize_alert_record,
    validate_and_normalize_asset_record,
    validate_and_normalize_case_record,
)


def parse_raw_file(content: bytes, filename: str) -> Tuple[List[str], List[Dict[str, Any]], str]:
    """
    Safely parse raw bytes into (columns, raw_rows_list, detected_extension).
    Never crashes on malformed lines or encoding quirks.
    """
    fn = filename.lower()
    if fn.endswith(".json"):
        text = content.decode("utf-8", errors="replace").strip()
        if not text:
            return ([], [], "json")
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                rows = parsed
            elif isinstance(parsed, dict):
                # If wrapped in a data key
                if "data" in parsed and isinstance(parsed["data"], list):
                    rows = parsed["data"]
                elif "alerts" in parsed and isinstance(parsed["alerts"], list):
                    rows = parsed["alerts"]
                elif "records" in parsed and isinstance(parsed["records"], list):
                    rows = parsed["records"]
                else:
                    rows = [parsed]
            else:
                rows = []

            if not rows:
                return ([], [], "json")

            # Collect columns from keys across records
            cols = []
            seen = set()
            for r in rows:
                if isinstance(r, dict):
                    for k in r.keys():
                        if k not in seen:
                            seen.add(k)
                            cols.append(k)

            return (cols, rows, "json")
        except json.JSONDecodeError:
            # Fallback to line-delimited JSON (JSONL)
            rows = []
            cols = []
            seen = set()
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        rows.append(obj)
                        for k in obj.keys():
                            if k not in seen:
                                seen.add(k)
                                cols.append(k)
                except Exception:
                    continue
            return (cols, rows, "json")

    # CSV / TSV / TXT parsing
    text = content.decode("utf-8", errors="replace")
    if not text.strip():
        return ([], [], "csv")

    # Detect delimiter
    sample = text[:4096]
    delimiter = ","
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters=",\t|;")
        delimiter = dialect.delimiter
    except Exception:
        delimiter = ","

    f_io = io.StringIO(text)
    reader = csv.reader(f_io, delimiter=delimiter)

    rows = []
    headers = []
    for i, row in enumerate(reader):
        if not row or all(c.strip() == "" for c in row):
            continue
        if not headers:
            headers = [c.strip() for c in row]
            continue
        # Map row to header
        row_dict = {}
        for j, col_name in enumerate(headers):
            val = row[j].strip() if j < len(row) else None
            row_dict[col_name] = val
        rows.append(row_dict)

    return (headers, rows, "csv")


def process_uploaded_file(
    content: bytes,
    filename: str,
    db: Session,
    duplicate_policy: str = "keep_first", # keep_first, reject_all
    max_preview_rows: int = 50,
) -> domain.DatasetUpload:
    """
    Main Ingestion Pipeline:
    1. Parse raw CSV/JSON safely.
    2. Detect schema type (alerts/assets/cases).
    3. Validate and normalize records.
    4. Detect duplicates.
    5. Calculate quality metrics.
    6. Ensure CSE entity records exist.
    7. Atomically save DatasetUpload and domain records.
    """
    upload_id = str(uuid.uuid4())
    headers, raw_rows, file_type = parse_raw_file(content, filename)

    records_received = len(raw_rows)
    if records_received == 0:
        # Empty file
        upload = domain.DatasetUpload(
            id=upload_id,
            filename=filename,
            file_type=file_type,
            dataset_type="unknown",
            uploaded_at=datetime.datetime.utcnow(),
            status="rejected",
            records_received=0,
            records_valid=0,
            records_rejected=0,
            warnings_count=1,
            errors_count=1,
            columns_detected=headers,
            quality_report={"error": "File is empty or contains no parseable records"},
            error_details=["Empty dataset submitted"],
            entity_ids=[],
        )
        db.add(upload)
        db.commit()
        db.refresh(upload)
        return upload

    # Detect dataset type
    dataset_type = detect_dataset_type(headers)
    column_mapping = map_columns_to_canonical(headers, dataset_type)

    valid_canonical_records: List[Dict[str, Any]] = []
    seen_ids = set()
    duplicate_count = 0
    records_rejected = 0
    all_warnings: List[str] = []
    all_errors: List[str] = []
    detected_entities = set()
    date_starts = []
    date_ends = []

    quality_summary = {
        "missing_timestamps": 0,
        "invalid_timestamps": 0,
        "missing_entity_ids": 0,
        "duplicate_ids": 0,
        "unknown_severity": 0,
        "missing_criticality": 0,
        "non_standard_booleans": 0,
    }

    for idx, row in enumerate(raw_rows):
        if dataset_type == "alerts":
            canonical, is_valid, errs, warns, q_inc = validate_and_normalize_alert_record(row, column_mapping, idx)
        elif dataset_type == "assets":
            canonical, is_valid, errs, warns, q_inc = validate_and_normalize_asset_record(row, column_mapping, idx)
        elif dataset_type == "cases":
            canonical, is_valid, errs, warns, q_inc = validate_and_normalize_case_record(row, column_mapping, idx)
        else:
            canonical, is_valid, errs, warns, q_inc = validate_and_normalize_alert_record(row, column_mapping, idx)

        # Update quality increments
        for k, v in q_inc.items():
            quality_summary[k] = quality_summary.get(k, 0) + v

        all_warnings.extend(warns)
        all_errors.extend(errs)

        if not is_valid or not canonical:
            records_rejected += 1
            continue

        # Duplicate ID Check
        rec_id = canonical["id"]
        if rec_id in seen_ids:
            duplicate_count += 1
            quality_summary["duplicate_ids"] += 1
            if duplicate_policy == "keep_first":
                all_warnings.append(f"Row {idx+1}: duplicate ID '{rec_id}' detected (kept first occurrence)")
                records_rejected += 1
                continue
            else:
                all_errors.append(f"Row {idx+1}: duplicate ID '{rec_id}' rejected")
                records_rejected += 1
                continue

        seen_ids.add(rec_id)

        # Collect entities
        if "entity_id" in canonical and canonical["entity_id"]:
            detected_entities.add(canonical["entity_id"])

        # Collect timestamp range
        if "timestamp" in canonical and canonical["timestamp"]:
            date_starts.append(canonical["timestamp"])
            date_ends.append(canonical["timestamp"])
        elif "created_at" in canonical and canonical["created_at"]:
            date_starts.append(canonical["created_at"])
            date_ends.append(canonical["created_at"])

        valid_canonical_records.append(canonical)

    records_valid = len(valid_canonical_records)

    # Determine overall upload status
    if records_valid == 0:
        status = "rejected"
    elif records_rejected > 0 or len(all_warnings) > 0 or quality_summary["unknown_severity"] > 0:
        status = "validated_with_warnings"
    else:
        status = "validated"

    dt_start = min(date_starts) if date_starts else None
    dt_end = max(date_ends) if date_ends else None

    # 1. Ensure CSE entities exist in the database for foreign key consistency
    for eid in detected_entities:
        existing_entity = db.query(domain.Entity).filter(domain.Entity.id == eid).first()
        if not existing_entity:
            new_entity = domain.Entity(
                id=eid,
                name=f"Entity {eid}",
                sector="General",
                assessment_period=f"{datetime.datetime.utcnow().year}-Q{(datetime.datetime.utcnow().month-1)//3 + 1}"
            )
            db.add(new_entity)

    # 2. Create DatasetUpload record
    upload_record = domain.DatasetUpload(
        id=upload_id,
        filename=filename,
        file_type=file_type,
        dataset_type=dataset_type,
        uploaded_at=datetime.datetime.utcnow(),
        status=status,
        records_received=records_received,
        records_valid=records_valid,
        records_rejected=records_rejected,
        warnings_count=len(all_warnings),
        errors_count=len(all_errors),
        columns_detected=headers,
        quality_report=quality_summary,
        error_details=(all_errors + all_warnings)[:50], # Store top 50 notices
        entity_ids=list(detected_entities),
        date_range_start=dt_start,
        date_range_end=dt_end,
        source_hash=hashlib.sha256(content).hexdigest(),
        hash_algorithm="SHA-256",
        hash_created_at=datetime.datetime.utcnow(),
    )
    db.add(upload_record)
    db.flush()

    # 3. Bulk Insert Valid Records
    if dataset_type == "alerts":
        for rec in valid_canonical_records:
            alert_obj = domain.Alert(
                id=rec["id"],
                upload_id=upload_id,
                entity_id=rec["entity_id"],
                timestamp=rec["timestamp"],
                severity=rec["severity"],
                category=rec["category"],
                asset_id=rec.get("asset_id"),
                acknowledged=rec.get("acknowledged", False),
                investigation_started=rec.get("investigation_started", False),
                escalated=rec.get("escalated", False),
                closed_at=rec.get("closed_at"),
                disposition=rec.get("disposition"),
                investigation_duration_mins=rec.get("investigation_duration_mins"),
                closure_duration_mins=rec.get("closure_duration_mins"),
                raw_data=rec.get("raw_data"),
            )
            db.merge(alert_obj) # Use merge to prevent PK collisions with seeded data

    elif dataset_type == "assets":
        for rec in valid_canonical_records:
            asset_obj = domain.Asset(
                id=rec["id"],
                upload_id=upload_id,
                entity_id=rec["entity_id"],
                type=rec.get("type"),
                criticality=rec.get("criticality"),
                has_telemetry=rec.get("has_telemetry", True),
                raw_data=rec.get("raw_data"),
            )
            db.merge(asset_obj)

    elif dataset_type == "cases":
        for rec in valid_canonical_records:
            case_obj = domain.Case(
                id=rec["id"],
                upload_id=upload_id,
                entity_id=rec["entity_id"],
                alert_id=rec.get("alert_id"),
                created_at=rec["created_at"],
                investigator=rec.get("investigator"),
                investigation_duration=rec.get("investigation_duration", 0.0),
                escalation_status=rec.get("escalation_status", False),
                closure_time=rec.get("closure_time"),
                closure_reason=rec.get("closure_reason"),
                evidence_count=rec.get("evidence_count", 0),
                raw_data=rec.get("raw_data"),
            )
            db.merge(case_obj)

    db.commit()
    db.refresh(upload_record)

    # Record Audit Events for Module 9
    try:
        from app.services.audit import AuditService, EventType, ActorType
        audit_svc = AuditService()
        primary_entity = list(detected_entities)[0] if detected_entities else "CSE-001"

        audit_svc.record_event(
            db=db,
            event_type=EventType.DATA_INGESTED,
            actor_type=ActorType.SYSTEM,
            actor_id="IngestionService",
            entity_id=primary_entity,
            analysis_id=upload_id,
            payload={
                "upload_id": upload_id,
                "filename": filename,
                "file_type": file_type,
                "dataset_type": dataset_type,
                "records_received": records_received,
                "source_hash": upload_record.source_hash,
            },
        )

        audit_svc.record_event(
            db=db,
            event_type=EventType.DATA_VALIDATED,
            actor_type=ActorType.SYSTEM,
            actor_id="ValidationService",
            entity_id=primary_entity,
            analysis_id=upload_id,
            payload={
                "upload_id": upload_id,
                "status": status,
                "records_valid": records_valid,
                "records_rejected": records_rejected,
                "warnings_count": len(all_warnings),
                "errors_count": len(all_errors),
                "entities_detected": list(detected_entities),
            },
        )
    except Exception as e:
        # Prevent audit event failure from breaking ingestion pipeline
        pass

    return upload_record


def get_upload_preview_data(upload_id: str, db: Session, limit: int = 50) -> Optional[Dict[str, Any]]:
    """
    Fetch preview data specifically belonging to a single upload.
    """
    upload = db.query(domain.DatasetUpload).filter(domain.DatasetUpload.id == upload_id).first()
    if not upload:
        return None

    # Fetch rows based on dataset_type
    records = []
    if upload.dataset_type == "alerts":
        alerts = db.query(domain.Alert).filter(domain.Alert.upload_id == upload_id).limit(limit).all()
        for a in alerts:
            records.append({
                "id": a.id,
                "entity_id": a.entity_id,
                "timestamp": a.timestamp.isoformat() if a.timestamp else None,
                "severity": a.severity,
                "category": a.category,
                "asset_id": a.asset_id,
                "acknowledged": a.acknowledged,
                "investigation_started": a.investigation_started,
                "escalated": a.escalated,
                "disposition": a.disposition,
                "investigation_duration_mins": a.investigation_duration_mins,
                "closure_duration_mins": a.closure_duration_mins,
            })
    elif upload.dataset_type == "assets":
        assets = db.query(domain.Asset).filter(domain.Asset.upload_id == upload_id).limit(limit).all()
        for ast in assets:
            records.append({
                "id": ast.id,
                "entity_id": ast.entity_id,
                "type": ast.type,
                "criticality": ast.criticality,
                "has_telemetry": ast.has_telemetry,
            })
    elif upload.dataset_type == "cases":
        cases = db.query(domain.Case).filter(domain.Case.upload_id == upload_id).limit(limit).all()
        for c in cases:
            records.append({
                "id": c.id,
                "entity_id": c.entity_id,
                "alert_id": c.alert_id,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "investigator": c.investigator,
                "investigation_duration": c.investigation_duration,
                "escalation_status": c.escalation_status,
                "closure_reason": c.closure_reason,
            })

    return {
        "upload_id": upload.id,
        "filename": upload.filename,
        "file_type": upload.file_type,
        "dataset_type": upload.dataset_type,
        "status": upload.status,
        "records_received": upload.records_received,
        "records_valid": upload.records_valid,
        "records_rejected": upload.records_rejected,
        "warnings_count": upload.warnings_count,
        "errors_count": upload.errors_count,
        "columns_detected": upload.columns_detected or [],
        "quality": upload.quality_report or {},
        "entities": upload.entity_ids or [],
        "date_range_start": upload.date_range_start.isoformat() if upload.date_range_start else None,
        "date_range_end": upload.date_range_end.isoformat() if upload.date_range_end else None,
        "total_preview_records": len(records),
        "data": records,
    }
