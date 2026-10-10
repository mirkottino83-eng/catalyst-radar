import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from offhours_news import build_news_watch, QUERIES, classify_geo

SAT = datetime(2026,10,10,18,0,tzinfo=timezone.utc)

class TestWeekendNews(unittest.TestCase):
    def test_saturday_news_without_market_data(self):
        calls=[]
        def fetch(q,limit):
            calls.append(q)
            if "Iran OR Israel" in q:
                return [{"title":"Iran sanctions and oil tanker shipping threats continue",
                         "source":"Associated Press",
                         "published":SAT-timedelta(minutes=12),
                         "url":"https://example.org/iran"}]
            if "Nvidia OR AMD" in q:
                return [{"title":"Nvidia announces major AI supply agreement on Saturday",
                         "source":"Reuters",
                         "published":SAT-timedelta(minutes=20),
                         "url":"https://example.org/nvidia"}]
            return []
        result=build_news_watch(fetch,SAT)
        self.assertEqual(len(calls),len(QUERIES))
        self.assertEqual(len(result["geopolitics"]),1)
        self.assertEqual(len(result["corporate"]),1)
        self.assertEqual(result["geopolitics"][0]["verification_status"],
                         "INDICE_RSS_DA_VERIFICARE")
        self.assertFalse(result["open_market_required"])

    def test_ceasefire_anniversary_killings_are_not_peace(self):
        self.assertEqual(classify_geo("Child among eight killed on ceasefire anniversary"),
                         "POSSIBILE_ESCALATION_DA_VERIFICARE")
        self.assertEqual(classify_geo("Sides announce ceasefire deal after peace talks"),
                         "POSSIBILE_DISTENSIONE_DA_VERIFICARE")
        self.assertEqual(classify_geo("One year after ceasefire, diplomatic opinions differ"),
                         "CONTESTO_NON_CLASSIFICATO")

    def test_filter_better_buy_comparison_articles(self):
        def fetch(q,n):
            return [{"title":"Broadcom vs. Intel: Which Chip Stock Is a Better Buy?",
                     "published":SAT-timedelta(minutes=4),
                     "url":"https://example.org/opinion","source":"Financial news"},
                    {"title":"Intel announces new multi-year chip supply agreement",
                     "published":SAT-timedelta(minutes=6),
                     "url":"https://example.org/contract","source":"Wire"}]
        result=build_news_watch(fetch,SAT)
        self.assertTrue(result["corporate"])
        self.assertTrue(all("better buy" not in x["title"].lower() for x in result["corporate"]))
        self.assertTrue(any("supply agreement" in x["title"].lower() for x in result["corporate"]))

    def test_zero_does_not_hide_feed_error(self):
        def fetch(q,limit):
            if "Russia OR Ukraine" in q: raise TimeoutError("feed unavailable")
            return []
        result=build_news_watch(fetch,SAT)
        self.assertEqual(result["status"],"SOURCE_ERRORS")
        self.assertEqual(
            next(s for s in result["sources"] if s["area"]=="Russia / Ucraina")["status"],"ERROR")
        self.assertEqual(result["geopolitics"],[])

    def test_reject_undated_future_and_very_old(self):
        articles=[
            {"title":"US tariffs change semiconductor export rules","published":None,"url":"https://example.org/a"},
            {"title":"US tariffs change semiconductor export rules","published":SAT+timedelta(hours=3),"url":"https://example.org/b"},
            {"title":"US tariffs change semiconductor export rules","published":SAT-timedelta(hours=60),"url":"https://example.org/c"},
        ]
        r=build_news_watch(lambda q,n:articles,SAT)
        self.assertEqual(r["geopolitics"],[])
        self.assertEqual(r["corporate"],[])

    def test_deduplicate_and_sort(self):
        old={"title":"Iran attack on tankers prompts sanctions",
             "published":SAT-timedelta(hours=2),
             "source":"Reuters","url":"https://example.org/a"}
        new={**old,"published":SAT-timedelta(minutes=3),"url":"https://example.org/b"}
        r=build_news_watch(lambda q,n:[new,new,old],SAT)
        self.assertEqual(len(r["geopolitics"]),1)
        self.assertEqual(r["geopolitics"][0]["url"],"https://example.org/b")

if __name__=="__main__": unittest.main()
