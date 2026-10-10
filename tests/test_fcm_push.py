import sys
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fcm_push

NOW = datetime(2026, 10, 9, 15, 15, tzinfo=timezone.utc)

def candidate():
    return {
        "id": "news-1", "ticker": "AMD", "headline": "AMD wins large supply agreement",
        "catalyst_type": "large_contract",
        "published_at": (NOW - timedelta(minutes=5)).isoformat(),
        "verification_status": "RSS_INDICIZZATO_DA_VERIFICARE",
        "source": "Reuters",
        "factors": {"source_quality": 95, "catalyst_strength": 88},
        "quote_status": "STALE", "satispay_status": "check",
        "current_change_pct": None, "relative_volume": None,
        "short_term_change_pct": None, "confidence_score": 70,
    }

class FCMTests(unittest.TestCase):
    def test_topic_contract(self):
        self.assertEqual(fcm_push.TOPICS["catalyst"], "catalyst-alerts")
        self.assertEqual(fcm_push.TOPICS["macro"], "tech-macro")

    def test_dedup_per_backend_and_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            calls = []
            publisher = lambda alert: calls.append(alert["key"])
            first = fcm_push.send_prepared(
                [candidate()], {}, {}, NOW, publisher, path
            )
            self.assertEqual(first, 1)
            self.assertEqual(len(calls), 1)
            again = fcm_push.send_prepared(
                [candidate()], {}, {}, NOW, publisher, path
            )
            self.assertEqual(again, 0)
            self.assertEqual(len(calls), 1)

    def test_failed_send_does_not_mark_delivered(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            def fail(_):
                raise RuntimeError("offline")
            self.assertEqual(
                fcm_push.send_prepared([candidate()], {}, {}, NOW, fail, path), 0
            )
            self.assertEqual(len(fcm_push.read_state(path).get("sent", {})), 0)

    def test_data_only_payload(self):
        class Response:
            def raise_for_status(self): pass
        class Client:
            def __init__(self): self.request = None
            def post(self, url, **kwargs):
                self.request = (url, kwargs)
                return Response()
        client = Client()
        payload = {"key": "abc", "kind": "catalyst",
                   "title": "Catalyst Radar", "message": "test"}
        fcm_push.publish_fcm(payload, "project-example-123", "dummy", client)
        url, options = client.request
        self.assertEqual(
            options["json"]["message"]["topic"], "catalyst-alerts"
        )
        self.assertNotIn("notification", options["json"]["message"])
        self.assertEqual(options["json"]["message"]["android"]["ttl"], "900s")

if __name__ == "__main__":
    unittest.main()
