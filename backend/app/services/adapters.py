"""
SAT-SA Dataset Adapters & Canonical Schema Mapping
Maps raw and external dataset formats (SALAD-SOC, AI-SOC, custom SOC exports)
into canonical SAT-SA domain schemas.
"""

from typing import Dict, Any, List, Tuple
from app.services.normalization import normalize_column_name


# Canonical Fields
ALERT_CANONICAL_FIELDS = {
    "alert_id": {"required": True, "type": "string"},
    "timestamp": {"required": True, "type": "datetime"},
    "severity": {"required": False, "type": "string", "default": "Medium"},
    "category": {"required": False, "type": "string", "default": "General Alert"},
    "entity_id": {"required": False, "type": "string", "default": "CSE-001"},
    "asset_id": {"required": False, "type": "string", "default": None},
    "acknowledged": {"required": False, "type": "boolean", "default": False},
    "investigation_started": {"required": False, "type": "boolean", "default": False},
    "escalated": {"required": False, "type": "boolean", "default": False},
    "closed_at": {"required": False, "type": "datetime", "default": None},
    "disposition": {"required": False, "type": "string", "default": None},
    "investigation_duration_mins": {"required": False, "type": "float", "default": None},
    "closure_duration_mins": {"required": False, "type": "float", "default": None},
}

ASSET_CANONICAL_FIELDS = {
    "asset_id": {"required": True, "type": "string"},
    "entity_id": {"required": False, "type": "string", "default": "CSE-001"},
    "type": {"required": False, "type": "string", "default": "Server"},
    "criticality": {"required": False, "type": "string", "default": "Medium"},
    "has_telemetry": {"required": False, "type": "boolean", "default": True},
}

CASE_CANONICAL_FIELDS = {
    "case_id": {"required": True, "type": "string"},
    "entity_id": {"required": False, "type": "string", "default": "CSE-001"},
    "alert_id": {"required": False, "type": "string", "default": None},
    "created_at": {"required": True, "type": "datetime"},
    "investigator": {"required": False, "type": "string", "default": None},
    "investigation_duration": {"required": False, "type": "float", "default": 0.0},
    "escalation_status": {"required": False, "type": "boolean", "default": False},
    "closure_time": {"required": False, "type": "datetime", "default": None},
    "closure_reason": {"required": False, "type": "string", "default": None},
    "evidence_count": {"required": False, "type": "int", "default": 0},
}


# Generic column aliases mapping to canonical names
GENERIC_ALERT_ALIASES = {
    "alert_id": ["id", "alertid", "alert_identifier", "event_id", "record_id", "alert_no", "incident_id", "uuid"],
    "entity_id": ["entity", "cse_id", "entity_code", "organization", "org_id", "tenant_id", "source_dataset", "network_segment"],
    "timestamp": ["time", "datetime", "date", "event_time", "alert_time", "timestamp_utc", "ts", "created_at", "start_time"],
    "severity": ["sev", "severity_level", "priority", "alert_severity", "level", "urgency", "impact"],
    "category": ["type", "alert_type", "attack_type", "attack_category", "tactic", "mitre_tactic", "signature", "rule_name", "category_name"],
    "asset_id": ["asset", "hostname", "host", "destination_ip", "dst_ip", "target_asset", "ip", "endpoint", "device_id"],
    "acknowledged": ["ack", "is_acknowledged", "acknowledged_flag", "acknowledged_status"],
    "investigation_started": ["investigated", "is_investigated", "investigation_flag", "in_progress"],
    "escalated": ["is_escalated", "escalate", "escalated_flag", "escalation", "tier_escalated", "triage_decision"],
    "closed_at": ["closed_time", "resolved_at", "resolved_time", "end_time", "closure_timestamp"],
    "disposition": ["resolution", "status", "outcome", "close_reason", "decision", "action_taken"],
    "investigation_duration_mins": ["investigation_duration", "investigation_time", "duration_mins", "analysis_duration"],
    "closure_duration_mins": ["closure_duration", "time_to_close", "resolution_duration", "duration"],
}

GENERIC_ASSET_ALIASES = {
    "asset_id": ["id", "assetid", "hostname", "host", "device_id", "machine_id", "endpoint_id"],
    "entity_id": ["entity", "cse_id", "organization", "org_id", "business_unit", "dept"],
    "type": ["asset_type", "device_type", "category", "system_type", "kind"],
    "criticality": ["crit", "asset_criticality", "priority", "importance", "tier"],
    "has_telemetry": ["telemetry", "is_monitored", "logging_enabled", "monitored", "has_logs"],
}

GENERIC_CASE_ALIASES = {
    "case_id": ["id", "caseid", "incident_id", "ticket_id", "ticket_no"],
    "entity_id": ["entity", "cse_id", "organization", "org_id"],
    "alert_id": ["alert", "alertid", "source_alert_id", "linked_alert"],
    "created_at": ["timestamp", "time", "datetime", "opened_at", "date"],
    "investigator": ["assigned_to", "analyst", "owner", "operator", "user"],
    "investigation_duration": ["duration", "investigation_time", "duration_mins"],
    "escalation_status": ["escalated", "is_escalated", "escalation"],
    "closure_time": ["closed_at", "closed_time", "resolved_at"],
    "closure_reason": ["disposition", "resolution", "reason", "outcome"],
    "evidence_count": ["evidences", "artifacts_count", "files_count"],
}


def detect_dataset_type(raw_columns: List[str]) -> str:
    """
    Intelligently infer dataset type (alerts, assets, cases) from column names.
    """
    normalized_cols = [normalize_column_name(c) for c in raw_columns]
    col_set = set(normalized_cols)

    # Check for Cases
    if "case_id" in col_set or "ticket_id" in col_set or "investigator" in col_set or "closure_reason" in col_set:
        return "cases"

    # Check for Assets
    if ("asset_id" in col_set or "hostname" in col_set) and ("criticality" in col_set or "asset_type" in col_set or "has_telemetry" in col_set):
        if not ("severity" in col_set or "alert_type" in col_set or "flow_duration" in col_set):
            return "assets"

    # Check for Alerts (Default for security logs/events)
    alert_indicators = {"alert_id", "alert_type", "severity", "timestamp", "flow_duration", "src_ip", "dst_ip", "attack_category", "triage_decision"}
    if col_set.intersection(alert_indicators):
        return "alerts"

    # Default to alerts
    return "alerts"


def map_columns_to_canonical(raw_columns: List[str], dataset_type: str = "alerts") -> Dict[str, str]:
    """
    Produce a mapping from original raw column name -> canonical field name.
    """
    alias_dict = (
        GENERIC_ALERT_ALIASES if dataset_type == "alerts" else
        GENERIC_ASSET_ALIASES if dataset_type == "assets" else
        GENERIC_CASE_ALIASES
    )

    column_mapping = {}
    normalized_to_raw = {normalize_column_name(c): c for c in raw_columns}

    for canonical_field, aliases in alias_dict.items():
        # Direct match first
        if canonical_field in normalized_to_raw:
            column_mapping[normalized_to_raw[canonical_field]] = canonical_field
            continue

        # Check aliases
        for alias in aliases:
            if alias in normalized_to_raw:
                column_mapping[normalized_to_raw[alias]] = canonical_field
                break

    return column_mapping
