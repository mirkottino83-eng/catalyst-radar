"""Off-hours news discovery independent of exchange trading data.

This is an informational RSS digest, NOT a verified catalyst and never a
price-action or buy/sell signal. Do not suppress on weekends or market closure.
"""
import re
from datetime import datetime, timezone, timedelta

QUERIES = (
    ("geopolitics", "Medio Oriente / energia",
     '(Iran OR Israel OR Houthi OR "Strait of Hormuz" OR "Red Sea") '
     '(attack OR strike OR sanctions OR oil OR shipping OR ceasefire OR talks) when:2d'),
    ("geopolitics", "Russia / Ucraina",
     '(Russia OR Ukraine OR "Black Sea") '
     '(drone OR missile OR sanctions OR ceasefire OR oil OR gas OR pipeline) when:2d'),
    ("geopolitics", "USA / Cina / Taiwan",
     '(China OR Taiwan OR "US-China") '
     '("export controls" OR tariffs OR chips OR sanctions OR military OR trade) when:2d'),
    ("corporate", "Titoli tech e AI",
     '(Nvidia OR AMD OR Intel OR Alphabet OR Micron OR Nebius) '
     '(earnings OR guidance OR contract OR deal OR acquisition OR chips OR AI) when:2d'),
    ("corporate", "Farmaceutica e settori",
     '(Moderna OR Pfizer OR "FDA approval" OR "biotech" OR "energy stocks") '
     '(FDA OR trial OR earnings OR contract OR sanctions OR merger) when:2d')
)

EVENT_TOKENS = (
    "attack", "strike", "missile", "drone", "sanction", "ceasefire",
    "peace", "blockade", "pipeline", "shipping", "tariff", "export",
    "trade", "oil", "gas", "agreement", "negotiat", "warn", "threat",
    "contract", "earnings", "guidance", "fda", "trial", "merger",
    "acquisition", "partnership", "deal", "chip", "semiconductor",
    "investment", "approval", "launch", "supply"
)
ESCALATION = ("attack", "strike", "missile", "sanction", "blockade",
              "seized", "threat", "drone", "war")
DEESCALATION = ("ceasefire", "truce", "peace", "negotiat", "reopen", "talks")

def _date(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    return value.astimezone(timezone.utc)

def classify_geo(title):
    low = (title or "").lower()
    if any(x in low for x in ESCALATION):
        return "POSSIBILE_ESCALATION_DA_VERIFICARE"
    if any(x in low for x in DEESCALATION):
        return "POSSIBILE_DISTENSIONE_DA_VERIFICARE"
    return "CONTESTO_NON_CLASSIFICATO"

def build_news_watch(fetch_news, at=None):
    at = at or datetime.now(timezone.utc)
    records = {"geopolitics": [], "corporate": []}
    seen = {"geopolitics": set(), "corporate": set()}
    sources = []
    for kind, area, query in QUERIES:
        info = {"area": area, "status": "OK", "fetched": 0,
                "recent": 0, "accepted": 0}
        try:
            found = fetch_news(query, 16)
            if not isinstance(found, list):
                raise TypeError("News source returned invalid type")
            info["fetched"] = len(found)
            if not found:
                info["status"] = "NO_RSS_ITEMS"
            for article in found:
                dt = _date(article.get("published"))
                if dt is None or not timedelta(0) <= at - dt <= timedelta(hours=48):
                    continue
                info["recent"] += 1
                title = str(article.get("title") or "").strip()
                if len(title) < 18 or not any(k in title.lower() for k in EVENT_TOKENS):
                    continue
                key = re.sub(r"\W+", " ", title.lower()).strip()
                if key in seen[kind]:
                    continue
                link = str(article.get("url") or "")
                if not link.startswith(("https://", "http://")):
                    continue
                seen[kind].add(key)
                records[kind].append({
                    "title": title[:260],
                    "source": str(article.get("source") or "Indice RSS")[:90],
                    "url": link,
                    "published_at": dt.isoformat(),
                    "area": area,
                    "classification": classify_geo(title) if kind == "geopolitics"
                                      else "NOTIZIA_SOCIETARIA_NON_VERIFICATA",
                    "verification_status": "INDICE_RSS_DA_VERIFICARE",
                })
                info["accepted"] += 1
            if found and not info["recent"]:
                info["status"] = "NO_RECENT_ITEMS"
            elif info["recent"] and not info["accepted"]:
                info["status"] = "FILTERED"
        except Exception as err:
            info["status"] = "ERROR"
            # No exception string: RSS errors can contain full URLs or sensitive tokens.
            info["error_type"] = type(err).__name__
        sources.append(info)
    for kind in records:
        records[kind] = sorted(records[kind],
                               key=lambda item: item["published_at"],reverse=True)[:16]
    return {
        "updated_at": at.isoformat(),
        "open_market_required": False,
        "window_hours": 48,
        "status": ("SOURCE_ERRORS" if any(s["status"] == "ERROR" for s in sources)
                   else "OK"),
        "sources": sources,
        "geopolitics": records["geopolitics"],
        "corporate": records["corporate"],
        "disclaimer": "RSS indicizzato, non notizia primaria verificata. Gli orari sono quelli degli articoli, non necessariamente dell'evento."
    }
