"""Apply an authenticated GitHub issue command.

Never honor the issue body; only exact predefined issue titles from the
repository owner can change the public, nonsensitive state file.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from control_state import CONTROL_PATH, load_control

ACTIONS = {
    "Catalyst Radar control: enable-monitoring": ("monitoring_enabled", True),
    "Catalyst Radar control: disable-monitoring": ("monitoring_enabled", False),
    "Catalyst Radar control: enable-notifications": ("notifications_enabled", True),
    "Catalyst Radar control: disable-notifications": ("notifications_enabled", False),
}

def apply_issue(title, author, owner, path=None):
    if not author or not owner or author != owner:
        raise PermissionError("Only the GitHub repository owner can change controls")
    if title not in ACTIONS:
        raise ValueError("Unknown control command")
    key, value = ACTIONS[title]
    target = Path(path) if path else CONTROL_PATH
    state = load_control(target)
    if state.get("control_error"):
        raise ValueError("Control configuration invalid; not overwriting")
    state[key] = value
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    state["changed_by"] = owner
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print(f"Control updated: {key}={value}")
    return state

if __name__ == "__main__":
    apply_issue(os.environ.get("CONTROL_ISSUE_TITLE",""),
                os.environ.get("CONTROL_ISSUE_AUTHOR",""),
                os.environ.get("CONTROL_REPO_OWNER",""))
