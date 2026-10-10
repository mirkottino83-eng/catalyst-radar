import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import push_alerts

NOW=datetime(2026,10,9,15,15,tzinfo=timezone.utc) # Fri, 11:15 NY

def market(at=NOW,stale=False):
    t=(at-timedelta(hours=3) if stale else at-timedelta(minutes=10)).isoformat()
    return {symbol:{"last_quote_at":t} for symbol in push_alerts.REQUIRED_MACRO}

def macro():
    return dict(tech_bias="strong_positive",macro_score=85,
                nasdaq_change_pct=1.2,sox_change_pct=1.8,
                vix_change_pct=-3.0,treasury_10y_change_bp=-2,
                wti_change_pct=-0.5,geopolitical_risk_score=35)

def catalyst(at=NOW):
    return {"id":"headline123","ticker":"NVDA","headline":"Nvidia raises guidance",
            "source":"Reuters","published_at":(at-timedelta(minutes=10)).isoformat(),
            "quote_at":(at-timedelta(minutes=12)).isoformat(),
            "quote_status":"RECENT_UNOFFICIAL",
            "verification_status":"RSS_INDICIZZATO_DA_VERIFICARE",
            "confidence_score":83,"current_change_pct":1.2,
            "short_term_change_pct":0.5,"relative_volume":1.8,
            "early_signal":True,"satispay_status":"check"}

class PushTests(unittest.TestCase):
    def test_candidates_and_duplicates(self):
        c=catalyst()
        alerts, favourable=push_alerts.make_alerts([c],macro(),market(),{},NOW)
        self.assertTrue(favourable)
        self.assertEqual({a["kind"] for a in alerts},{"macro","catalyst"})
        state={"sent":{c["id"]:NOW.isoformat()}, "last_by_ticker":{"NVDA":NOW.isoformat()},
               "macro_favorable":True}
        alerts,_=push_alerts.make_alerts([c],macro(),market(),state,NOW)
        self.assertEqual(alerts,[])

    def test_no_false_macro_when_quotes_stale_or_weekend(self):
        self.assertFalse(push_alerts.fresh_macro(macro(),market(stale=True),NOW))
        sat=NOW+timedelta(days=1)
        self.assertFalse(push_alerts.fresh_macro(macro(),market(sat),sat))
        missing=market()
        del missing["^SOX"]
        self.assertFalse(push_alerts.fresh_macro(macro(),missing,NOW))

    def test_stale_and_missing_news_never_push(self):
        c=catalyst()
        c["quote_at"]=(NOW-timedelta(hours=2)).isoformat()
        self.assertFalse(push_alerts.eligible_candidate(c,NOW))
        c=catalyst()
        c["verification_status"]="SEC_DOCUMENTO_UFFICIALE_EVENTO_NON_CLASSIFICATO"
        self.assertFalse(push_alerts.eligible_candidate(c,NOW))
        c=catalyst()
        c["satispay_status"]="unavailable"
        self.assertFalse(push_alerts.eligible_candidate(c,NOW))

    def test_opt_in_and_successful_delivery_only(self):
        original=push_alerts.STATE_PATH
        topic=os.environ.get("NTFY_TOPIC")
        with tempfile.TemporaryDirectory() as directory:
            push_alerts.STATE_PATH=Path(directory)/"alert_state.json"
            try:
                os.environ.pop("NTFY_TOPIC",None)
                self.assertFalse(push_alerts.run_alerts([catalyst()],macro(),market(),NOW)["configured"])
                self.assertFalse(push_alerts.STATE_PATH.exists())
                os.environ["NTFY_TOPIC"]="catalyst_radar_test_abcdef123456"
                sent=[]
                result=push_alerts.run_alerts([catalyst()],macro(),market(),NOW,
                    publisher=lambda topic, alert:sent.append(alert["kind"]))
                self.assertEqual(result["sent"],2)
                self.assertEqual(set(sent),{"macro","catalyst"})
                self.assertEqual(push_alerts.run_alerts([catalyst()],macro(),market(),NOW,
                    publisher=lambda topic,alert:sent.append(alert["kind"]))["sent"],0)
            finally:
                push_alerts.STATE_PATH=original
                if topic is None:os.environ.pop("NTFY_TOPIC",None)
                else:os.environ["NTFY_TOPIC"]=topic

if __name__=="__main__":
    unittest.main()
