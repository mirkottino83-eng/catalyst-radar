"""Optional Firebase Cloud Messaging sender.

FCM private key stays in a GitHub Actions secret; ONLY topic names, never user
tokens, are sent by the server. Each phone independently subscribes/unsubscribes.
No Firebase connection is attempted unless the service-account secret exists.
"""
import base64
import copy
import json
import os
import re
from datetime import timedelta
from pathlib import Path

import requests
from push_alerts import (
    HOME, make_alerts, read_time, utcnow
)

STATE_PATH = Path(__file__).resolve().parents[1] / "data" / "fcm_alert_state.json"
PROJECT_PATTERN = re.compile(r"^[a-z][a-z0-9-]{4,62}$")
TOPICS = {"catalyst": "catalyst-alerts", "macro": "tech-macro"}


def enabled():
    return bool(os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON_B64", "").strip())


def read_state(path=None):
    path = Path(path) if path else STATE_PATH
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError):
        return {}


def write_state(state, path=None):
    path = Path(path) if path else STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def get_authorization():
    """Called only in the GitHub Action. Never expose service account JSON."""
    encoded = os.environ["FIREBASE_SERVICE_ACCOUNT_JSON_B64"].strip()
    raw = json.loads(base64.b64decode(encoded, validate=True).decode("utf-8"))
    if raw.get("type") != "service_account":
        raise ValueError("Invalid FCM service account type")
    project = raw.get("project_id", "")
    if not PROJECT_PATTERN.fullmatch(project):
        raise ValueError("Invalid FCM project id")
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    credentials = service_account.Credentials.from_service_account_info(
        raw, scopes=["https://www.googleapis.com/auth/firebase.messaging"]
    )
    credentials.refresh(Request())
    return project, credentials.token


def publish_fcm(alert, project, access_token, http=requests):
    kind = alert["kind"]
    topic = TOPICS[kind]
    message = {
        "message": {
            "topic": topic,
            "data": {
                "title": str(alert["title"])[:100],
                "body": str(alert["message"])[:750],
                "url": HOME,
                "kind": kind,
                "alert_id": str(alert["key"])[:100],
            },
            "android": {
                "priority": "HIGH",
                "ttl": "900s"
            }
        }
    }
    response = http.post(
        f"https://fcm.googleapis.com/v1/projects/{project}/messages:send",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        },
        json=message,
        timeout=15
    )
    response.raise_for_status()


def send_prepared(catalysts, macro, market, at, publisher, state_path=None):
    """Persist ONLY messages accepted by FCM; leave failed transitions retryable."""
    state = copy.deepcopy(read_state(state_path))
    pending, favorable = make_alerts(catalysts, macro, market, state, at)
    state.setdefault("sent", {})
    state.setdefault("last_by_ticker", {})
    cutoff = at - timedelta(days=2)
    state["sent"] = {
        k: v for k, v in state["sent"].items()
        if (dt := read_time(v)) and dt >= cutoff
    }
    queued_macro = any(alert["kind"] == "macro" for alert in pending)
    sent_macro = False
    delivered = 0
    for alert in pending:
        try:
            publisher(alert)
        except Exception as error:
            # Only the exception TYPE is logged, never credentials or message content.
            print(f"FCM {alert['kind']} delivery failed: {type(error).__name__}")
            continue
        delivered += 1
        if alert["kind"] == "macro":
            sent_macro = True
            state["last_macro_sent"] = at.isoformat()
        else:
            state["sent"][alert["key"]] = at.isoformat()
            state["last_by_ticker"][alert["ticker"]] = at.isoformat()
        write_state(state, state_path)

    state["macro_favorable"] = favorable and (not queued_macro or sent_macro)
    state["updated_at"] = at.isoformat()
    write_state(state, state_path)
    return delivered


def run_fcm_alerts(catalysts, macro, market):
    if not enabled():
        print("FCM not configured: no Play Store notifications sent")
        return {"configured": False, "sent": 0}
    try:
        project, token = get_authorization()
        delivered = send_prepared(
            catalysts, macro, market, utcnow(),
            lambda alert: publish_fcm(alert, project, token),
        )
        print(f"FCM sender accepted {delivered} notification(s)")
        return {"configured": True, "sent": delivered}
    except Exception as error:
        print(f"FCM setup/send unavailable: {type(error).__name__}")
        return {"configured": False, "sent": 0}
