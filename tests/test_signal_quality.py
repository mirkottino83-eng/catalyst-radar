import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from signal_quality import (
    headline_status, hourly_change, hourly_relative_volume,
    quote_health, early_signal,
)

NOW = datetime(2026, 10, 9, 20, 0, tzinfo=timezone.utc)

class TestSignalQuality(unittest.TestCase):
    def test_news_timing_and_secondary_items(self):
        self.assertEqual(headline_status("ABC raises guidance", NOW - timedelta(minutes=5), NOW),
                         "NEW_RSS_UNVERIFIED")
        self.assertEqual(headline_status("ABC sponsorship charity donation", NOW, NOW),
                         "SECONDARY_OR_NON_FINANCIAL")
        self.assertEqual(headline_status("ABC previously announced contract", NOW, NOW),
                         "SECONDARY_OR_NON_FINANCIAL")
        self.assertEqual(headline_status("ABC raises guidance", NOW - timedelta(hours=7), NOW),
                         "OLD_NEWS")
        self.assertEqual(headline_status("ABC raises guidance", None, NOW),
                         "TIMESTAMP_NOT_VERIFIED")
        self.assertEqual(headline_status("ABC raises guidance", NOW + timedelta(hours=1), NOW),
                         "FUTURE_TIMESTAMP")

    def test_quotes_not_faked_when_stale(self):
        self.assertEqual(quote_health(None, NOW)["status"], "UNAVAILABLE")
        self.assertFalse(quote_health((NOW - timedelta(hours=2)).isoformat(), NOW)["is_recent"])
        self.assertTrue(quote_health((NOW - timedelta(minutes=7)).isoformat(), NOW)["is_recent"])

    def test_hourly_momentum_does_not_cross_sessions(self):
        fri_start = datetime(2026, 10, 9, 14, 30, tzinfo=timezone.utc)
        bars = [(int((fri_start+timedelta(minutes=5*i)).timestamp()), 100+i)
                for i in range(13)]
        self.assertAlmostEqual(hourly_change(bars), 12.0)
        # Two points one hour apart, but on different NY dates: no momentum.
        overnight = [
            (int(datetime(2026, 10, 8, 23, 30, tzinfo=timezone.utc).timestamp()), 100),
            (int(datetime(2026, 10, 9, 0, 30, tzinfo=timezone.utc).timestamp()), 110),
        ]
        # Those are same NY evening, so actually comparable.
        self.assertEqual(hourly_change(overnight), 10)
        cross_day = [
            (int(datetime(2026, 10, 9, 3, 30, tzinfo=timezone.utc).timestamp()), 100),
            (int(datetime(2026, 10, 9, 4, 30, tzinfo=timezone.utc).timestamp()), 110),
        ]
        self.assertIsNone(hourly_change(cross_day))

    def test_hourly_relative_volume_needs_prior_day(self):
        yesterday = datetime(2026, 10, 8, 14, 0, tzinfo=timezone.utc)
        today = datetime(2026, 10, 9, 14, 0, tzinfo=timezone.utc)
        rows = [(int((yesterday+timedelta(minutes=i*5)).timestamp()), 100) for i in range(13)]
        rows += [(int((today+timedelta(minutes=i*5)).timestamp()), 200) for i in range(13)]
        self.assertEqual(hourly_relative_volume(rows), 2)
        self.assertIsNone(hourly_relative_volume(rows[-13:]))

    def test_early_signal_requires_all_observations(self):
        self.assertTrue(early_signal(8, 1.1, 0.5, 1.8, True))
        self.assertFalse(early_signal(8, 5, 0.5, 1.8, True))
        self.assertFalse(early_signal(8, 1.1, None, 1.8, True))
        self.assertFalse(early_signal(8, 1.1, 0.5, None, True))

if __name__ == "__main__":
    unittest.main()
