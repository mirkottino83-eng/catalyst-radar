import sys
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import history


class HistoryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original = history.DEST
        history.DEST = Path(self.temp.name) / "history.json"

    def tearDown(self):
        history.DEST = self.original
        self.temp.cleanup()

    def test_checkpoints_and_reference_price(self):
        now = datetime(2026, 10, 10, 0, 0, tzinfo=timezone.utc)
        published = datetime(2026, 10, 9, 15, 0, tzinfo=timezone.utc)
        candidates = [{
            "id": "event-01", "ticker": "TEST", "company": "Test",
            "headline": "Test news", "source": "Test Feed",
            "published_at": published.isoformat(),
            "estimated_impact_pct": 3.0, "current_change_pct": 5.0,
            "confidence_score": 70, "verification_status": "DA_VERIFICARE"
        }]
        bars = [(int(published.timestamp()), 104.0),
                (int(published.timestamp()) + 2*3600, 105.0),
                (int(published.timestamp()) + 5*3600, 108.0),
                (int(published.timestamp()) + 8*3600, 102.0)]
        market = {"TEST": {
            "bars_5m": bars,
            "day_closes": [("2026-10-08", 100.0), ("2026-10-09", 106.0)]
        }}
        count, changed = history.update_history(candidates, market, now)
        self.assertEqual(count, 1)
        self.assertTrue(changed)
        event = history.load_history()["events"][0]
        self.assertEqual(event["pct_at_publication"], 4.0)
        self.assertAlmostEqual(event["checkpoints"]["2"]["return_pct"], 0.96)
        self.assertAlmostEqual(event["checkpoints"]["5"]["return_pct"], 3.85)
        self.assertAlmostEqual(event["checkpoints"]["8"]["return_pct"], -1.92)
        # Il registro resta disponibile anche quando la nuova scansione e' vuota.
        count, changed = history.update_history([], {}, now)
        self.assertEqual(count, 1)
        self.assertFalse(changed)

    def test_missing_price_is_not_faked(self):
        now = datetime(2026, 10, 9, 22, 0, tzinfo=timezone.utc)
        candidate = {"id": "event-02", "ticker": "TEST",
                     "headline": "No quote", "published_at": now.isoformat()}
        history.update_history([candidate], {"TEST": {}}, now)
        item = history.load_history()["events"][0]
        self.assertIsNone(item["price_at_publication"])
        self.assertIsNone(item["pct_at_publication"])
        self.assertIsNone(item["checkpoints"]["2"])

    def test_overnight_close_uses_same_day(self):
        ts = datetime(2026, 10, 9, 22, 0, tzinfo=timezone.utc)
        base = history.reference_close(
            [("2026-10-08", 100.0), ("2026-10-09", 105.0)], ts)
        self.assertEqual(base, 105.0)


if __name__ == "__main__":
    unittest.main()
