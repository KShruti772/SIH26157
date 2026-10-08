"""
SAT-SA Schema Validation Service
Validates individual records against canonical schemas (Alerts, Assets, Cases),
enforcing Required vs Optional vs Unknown field rules.
"""

from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from app.services.normalization import (
    normalize_null,
    normalize_severity,
    normalize_boolean,
    normalize_timestamp,
    normalize_float,
    normalize_int,
)
from app.services.adapters import (
    ALERT_CANONICAL_FIELDS,
    ASSET_CANONICAL_FIELDS,
    CASE_CANONICAL_FIELDS,
)


def validate_and_normalize_alert_record(
    raw_row: Dict[str, Any],
    column_mapping: Dict[str, str],
    row_index: int,
) -> Tuple[Optional[Dict[str, Any]], bool, List[str], List[str], Dict[str, int]]:
    """
    Validate and normalize a single alert record.
    Returns (canonical_dict, is_valid, errors, warnings, quality_increments)
    """
    errors = []
    warnings = []
    quality_inc = {
        "missing_timestamps": 0,
        "invalid_timestamps": 0,
        "missing_entity_ids": 0,
        "unknown_severity": 0,
        "non_standard_booleans": 0,
    }

    # Map raw fields to canonical names
    mapped_data: Dict[str, Any] = {}
    extra_data: Dict[str, Any] = {}

    for raw_k, raw_v in raw_row.items():
        v = normalize_null(raw_v)
        if raw_k in column_mapping:
            canonical_key = column_mapping[raw_k]
            mapped_data[canonical_key] = v
        else:
            if v is not None:
                extra_data[raw_k] = v

    # 1. Check Alert ID (Required)
    alert_id = mapped_data.get("alert_id")
    if not alert_id:
        # Check if id in extra data
        alert_id = extra_data.get("id") or extra_data.get("alertid") or f"AL-AUTO-{row_index+1:05d}"
        if not mapped_data.get("alert_id"):
            warnings.append(f"Row {row_index+1}: missing alert_id, assigned auto-ID '{alert_id}'")

    alert_id = str(alert_id).strip()

    # 2. Check Timestamp (Required)
    raw_ts = mapped_data.get("timestamp")
    if raw_ts is None:
        errors.append(f"Row {row_index+1} ({alert_id}): missing required timestamp")
        quality_inc["missing_timestamps"] += 1
        return (None, False, errors, warnings, quality_inc)

    dt, ts_warn, ts_valid = normalize_timestamp(raw_ts)
    if not ts_valid:
        errors.append(f"Row {row_index+1} ({alert_id}): invalid timestamp '{raw_ts}'")
        quality_inc["invalid_timestamps"] += 1
        return (None, False, errors, warnings, quality_inc)

    if ts_warn:
        warnings.append(f"Row {row_index+1} ({alert_id}): {ts_warn}")

    # 3. Entity ID (Optional with default)
    entity_id = mapped_data.get("entity_id")
    if not entity_id:
        entity_id = "CSE-001"
        quality_inc["missing_entity_ids"] += 1
        warnings.append(f"Row {row_index+1} ({alert_id}): missing entity_id, defaulted to 'CSE-001'")
    else:
        entity_id = str(entity_id).strip()

    # 4. Severity (Optional with normalization)
    raw_sev = mapped_data.get("severity", "Medium")
    severity, is_std_sev = normalize_severity(raw_sev)
    if not is_std_sev:
        quality_inc["unknown_severity"] += 1
        warnings.append(f"Row {row_index+1} ({alert_id}): non-standard severity '{raw_sev}' normalized to '{severity}'")

    # 5. Category (Optional)
    category = mapped_data.get("category") or extra_data.get("alert_type") or "General Alert"
    category = str(category).strip()

    # 6. Asset ID (Optional)
    asset_id = mapped_data.get("asset_id")
    if asset_id:
        asset_id = str(asset_id).strip()

    # 7. Booleans
    ack, ack_valid = normalize_boolean(mapped_data.get("acknowledged"), default=False)
    inv_started, inv_valid = normalize_boolean(mapped_data.get("investigation_started"), default=False)
    escalated, esc_valid = normalize_boolean(mapped_data.get("escalated"), default=False)

    if not (ack_valid and inv_valid and esc_valid):
        quality_inc["non_standard_booleans"] += 1

    # 8. Durations & Closed At
    closed_at = None
    raw_closed = mapped_data.get("closed_at")
    if raw_closed:
        c_dt, _, c_valid = normalize_timestamp(raw_closed)
        if c_valid:
            closed_at = c_dt

    disposition = mapped_data.get("disposition")
    if disposition:
        disposition = str(disposition).strip()

    inv_dur, _ = normalize_float(mapped_data.get("investigation_duration_mins"))
    cls_dur, _ = normalize_float(mapped_data.get("closure_duration_mins"))

    canonical_record = {
        "id": alert_id,
        "entity_id": entity_id,
        "timestamp": dt,
        "severity": severity,
        "category": category,
        "asset_id": asset_id,
        "acknowledged": ack,
        "investigation_started": inv_started,
        "escalated": escalated,
        "closed_at": closed_at,
        "disposition": disposition,
        "investigation_duration_mins": inv_dur,
        "closure_duration_mins": cls_dur,
        "raw_data": extra_data if extra_data else None,
    }

    return (canonical_record, True, errors, warnings, quality_inc)


def validate_and_normalize_asset_record(
    raw_row: Dict[str, Any],
    column_mapping: Dict[str, str],
    row_index: int,
) -> Tuple[Optional[Dict[str, Any]], bool, List[str], List[str], Dict[str, int]]:
    """Validate and normalize an asset record."""
    errors = []
    warnings = []
    quality_inc = {"missing_entity_ids": 0, "missing_criticality": 0}

    mapped_data = {}
    extra_data = {}

    for raw_k, raw_v in raw_row.items():
        v = normalize_null(raw_v)
        if raw_k in column_mapping:
            mapped_data[column_mapping[raw_k]] = v
        else:
            if v is not None:
                extra_data[raw_k] = v

    asset_id = mapped_data.get("asset_id") or extra_data.get("hostname")
    if not asset_id:
        errors.append(f"Row {row_index+1}: missing required asset_id")
        return (None, False, errors, warnings, quality_inc)

    asset_id = str(asset_id).strip()

    entity_id = mapped_data.get("entity_id") or "CSE-001"
    if not mapped_data.get("entity_id"):
        quality_inc["missing_entity_ids"] += 1
        warnings.append(f"Row {row_index+1} ({asset_id}): missing entity_id, defaulted to 'CSE-001'")

    asset_type = mapped_data.get("type") or extra_data.get("asset_type") or "Server"
    raw_crit = mapped_data.get("criticality")
    if not raw_crit:
        criticality = "Medium"
        quality_inc["missing_criticality"] += 1
    else:
        criticality, _ = normalize_severity(raw_crit)

    has_telemetry, _ = normalize_boolean(mapped_data.get("has_telemetry"), default=True)

    canonical_record = {
        "id": asset_id,
        "entity_id": str(entity_id).strip(),
        "type": str(asset_type).strip().title(),
        "criticality": criticality,
        "has_telemetry": has_telemetry,
        "raw_data": extra_data if extra_data else None,
    }

    return (canonical_record, True, errors, warnings, quality_inc)


def validate_and_normalize_case_record(
    raw_row: Dict[str, Any],
    column_mapping: Dict[str, str],
    row_index: int,
) -> Tuple[Optional[Dict[str, Any]], bool, List[str], List[str], Dict[str, int]]:
    """Validate and normalize a case record."""
    errors = []
    warnings = []
    quality_inc = {"missing_timestamps": 0, "invalid_timestamps": 0, "missing_entity_ids": 0}

    mapped_data = {}
    extra_data = {}

    for raw_k, raw_v in raw_row.items():
        v = normalize_null(raw_v)
        if raw_k in column_mapping:
            mapped_data[column_mapping[raw_k]] = v
        else:
            if v is not None:
                extra_data[raw_k] = v

    case_id = mapped_data.get("case_id")
    if not case_id:
        case_id = f"CASE-{row_index+1:05d}"
        warnings.append(f"Row {row_index+1}: missing case_id, auto-generated '{case_id}'")

    case_id = str(case_id).strip()

    raw_created = mapped_data.get("created_at")
    if not raw_created:
        errors.append(f"Row {row_index+1} ({case_id}): missing created_at timestamp")
        quality_inc["missing_timestamps"] += 1
        return (None, False, errors, warnings, quality_inc)

    dt, _, is_valid = normalize_timestamp(raw_created)
    if not is_valid:
        errors.append(f"Row {row_index+1} ({case_id}): invalid created_at timestamp '{raw_created}'")
        quality_inc["invalid_timestamps"] += 1
        return (None, False, errors, warnings, quality_inc)

    entity_id = mapped_data.get("entity_id") or "CSE-001"
    alert_id = mapped_data.get("alert_id")

    investigator = mapped_data.get("investigator")
    inv_dur, _ = normalize_float(mapped_data.get("investigation_duration"), default=0.0)
    esc_status, _ = normalize_boolean(mapped_data.get("escalation_status"), default=False)

    closure_time = None
    raw_closure = mapped_data.get("closure_time")
    if raw_closure:
        c_dt, _, c_valid = normalize_timestamp(raw_closure)
        if c_valid:
            closure_time = c_dt

    closure_reason = mapped_data.get("closure_reason")
    ev_count, _ = normalize_int(mapped_data.get("evidence_count"), default=0)

    canonical_record = {
        "id": case_id,
        "entity_id": str(entity_id).strip(),
        "alert_id": str(alert_id).strip() if alert_id else None,
        "created_at": dt,
        "investigator": str(investigator).strip() if investigator else None,
        "investigation_duration": inv_dur,
        "escalation_status": esc_status,
        "closure_time": closure_time,
        "closure_reason": str(closure_reason).strip() if closure_reason else None,
        "evidence_count": ev_count or 0,
        "raw_data": extra_data if extra_data else None,
    }

    return (canonical_record, True, errors, warnings, quality_inc)
