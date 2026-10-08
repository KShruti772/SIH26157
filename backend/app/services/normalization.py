"""
SAT-SA Normalization Service
Provides canonical field, type, timestamp, severity, and null normalizers.
"""

from datetime import datetime, timezone
from typing import Any, Optional, Tuple
import math
import re


def normalize_null(val: Any) -> Any:
    """Convert common null representations to Python None."""
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    if isinstance(val, str):
        cleaned = val.strip().lower()
        if cleaned in ("", "null", "none", "n/a", "na", "nan", "-", "undefined", "\\n", "nil"):
            return None
        return val.strip()
    return val


def normalize_column_name(col: str) -> str:
    """
    Convert varied column names into canonical snake_case.
    e.g. 'Alert ID' -> 'alert_id', 'alertId' -> 'alert_id', '  Timestamp (UTC) ' -> 'timestamp'
    """
    if not isinstance(col, str):
        col = str(col)
    s = col.strip()
    # Remove parenthesized notes like (UTC), [sec], etc.
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s).strip()
    # Handle camelCase -> camel_case
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    # Replace whitespace, hyphens, dots, slashes with underscores
    s = re.sub(r"[\s\-\./\\]+", "_", s)
    # Remove any non-alphanumeric/underscore
    s = re.sub(r"[^\w]", "", s)
    s = s.strip("_").lower()
    return s


def normalize_severity(val: Any) -> Tuple[str, bool]:
    """
    Normalize severity strings to canonical: 'Critical', 'High', 'Medium', 'Low', 'Unknown'.
    Returns (normalized_value, is_standard).
    """
    val = normalize_null(val)
    if val is None:
        return ("Unknown", False)

    s = str(val).strip().lower()

    if re.search(r"\b(crit|critical|sev\s*1|sev1|p1|priority\s*1|tier\s*1|fatal)\b", s):
        return ("Critical", True)
    if re.search(r"\b(high|sev\s*2|sev2|p2|priority\s*2|tier\s*2|major)\b", s):
        return ("High", True)
    if re.search(r"\b(med|medium|sev\s*3|sev3|p3|priority\s*3|tier\s*3|moderate|warn|warning)\b", s):
        return ("Medium", True)
    if re.search(r"\b(low|sev\s*4|sev4|p4|priority\s*4|tier\s*4|info|informational|minor|debug)\b", s):
        return ("Low", True)

    # If numeric 1-4
    if s in ("1", "1.0"):
        return ("Critical", True)
    if s in ("2", "2.0"):
        return ("High", True)
    if s in ("3", "3.0"):
        return ("Medium", True)
    if s in ("4", "4.0", "5", "5.0"):
        return ("Low", True)

    # Unrecognized severity
    return (str(val).strip().title() or "Unknown", False)


def normalize_boolean(val: Any, default: Optional[bool] = False) -> Tuple[bool, bool]:
    """
    Normalize boolean representations.
    Returns (normalized_bool, is_valid).
    """
    val = normalize_null(val)
    if val is None:
        return (default if default is not None else False, False)

    if isinstance(val, bool):
        return (val, True)

    if isinstance(val, (int, float)):
        if val == 1:
            return (True, True)
        if val == 0:
            return (False, True)

    s = str(val).strip().lower()
    if s in ("true", "t", "1", "yes", "y", "escalate", "escalated", "resolved", "closed", "pass", "ok", "ack", "acknowledged"):
        return (True, True)
    if s in ("false", "f", "0", "no", "n", "none", "unresolved", "open", "fail", "unack"):
        return (False, True)

    return (default if default is not None else False, False)


def normalize_timestamp(val: Any) -> Tuple[Optional[datetime], Optional[str], bool]:
    """
    Convert supported timestamps to UTC naive datetime.
    Returns (dt_object, warning_or_error_msg, is_valid).
    Policy: If timezone is missing, assumes UTC and sets warning 'timezone_assumed_utc'.
    """
    val = normalize_null(val)
    if val is None:
        return (None, "missing_timestamp", False)

    if isinstance(val, datetime):
        if val.tzinfo is not None:
            utc_dt = val.astimezone(timezone.utc).replace(tzinfo=None)
            return (utc_dt, None, True)
        return (val, "timezone_assumed_utc", True)

    # If numeric UNIX timestamp
    if isinstance(val, (int, float)):
        try:
            # Check if milliseconds or seconds
            ts = float(val)
            if ts > 1e11: # milliseconds
                ts /= 1000.0
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
            return (dt, None, True)
        except Exception:
            return (None, f"invalid_unix_timestamp: {val}", False)

    s = str(val).strip()
    if not s:
        return (None, "missing_timestamp", False)

    # Try numeric string
    if re.match(r"^\d{10,13}(\.\d+)?$", s):
        try:
            ts = float(s)
            if ts > 1e11:
                ts /= 1000.0
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
            return (dt, None, True)
        except Exception:
            pass

    # Try ISO formats
    try:
        # Replace Z with +00:00
        iso_str = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is not None:
            utc_dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return (utc_dt, None, True)
        return (dt, "timezone_assumed_utc", True)
    except Exception:
        pass

    # Try common formats
    common_formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S.%f",
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %I:%M:%S %p",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
    ]

    for fmt in common_formats:
        try:
            dt = datetime.strptime(s, fmt)
            return (dt, "timezone_assumed_utc", True)
        except ValueError:
            continue

    return (None, f"unparseable_timestamp: '{s}'", False)


def normalize_float(val: Any, default: Optional[float] = None) -> Tuple[Optional[float], bool]:
    """Safely parse float without raising exceptions."""
    val = normalize_null(val)
    if val is None:
        return (default, True if default is not None else False)
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return (default, False)
        return (f, True)
    except (ValueError, TypeError):
        return (default, False)


def normalize_int(val: Any, default: Optional[int] = None) -> Tuple[Optional[int], bool]:
    """Safely parse integer without raising exceptions."""
    val = normalize_null(val)
    if val is None:
        return (default, True if default is not None else False)
    try:
        # Handle string float like '5.0'
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return (default, False)
        return (int(f), True)
    except (ValueError, TypeError):
        return (default, False)
