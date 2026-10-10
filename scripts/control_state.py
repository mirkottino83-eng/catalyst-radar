"""GitHub-backed runtime switches for Catalyst Radar.

The public control file contains only non-secret booleans. Changes are
authorized by the repository owner's GitHub login via issue events.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROL_PATH = ROOT / "config" / "control.json"
DEFAULTS = {"monitoring_enabled": True, "notifications_enabled": True}

def load_control(path=None):
    target = Path(path) if path else CONTROL_PATH
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # Fail closed if a previously deployed config becomes unreadable.
        return {"monitoring_enabled": False, "notifications_enabled": False,
                "control_error": "CONFIG_UNREADABLE"}
    if not isinstance(raw, dict):
        return {"monitoring_enabled": False, "notifications_enabled": False,
                "control_error": "CONFIG_INVALID"}
    if any(type(raw.get(k)) is not bool for k in DEFAULTS):
        return {"monitoring_enabled": False, "notifications_enabled": False,
                "control_error": "CONFIG_INVALID"}
    return {**raw, "monitoring_enabled": raw["monitoring_enabled"],
            "notifications_enabled": raw["notifications_enabled"]}
