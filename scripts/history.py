"""Persistenza e misurazione verificabile dei catalyst di Catalyst Radar.

Le quotazioni yfinance sono dati non ufficiali e possono essere ritardate o
incomplete. Nessun prezzo/risultato viene inventato o sostituito con lo
snapshot corrente se manca la candela vicino all'istante richiesto.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "history.json"
NEW_YORK = ZoneInfo("America/New_York")
HORIZONS = (2, 5, 8)
QUOTE_TOLERANCE = 15 * 60
MAX_HISTORY_AGE_DAYS = 3650


def to_utc(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def from_bars(market_record):
    """(timestamp UTC in secondi, prezzo), solo se genuinamente disponibili."""
    result = []
    for row in market_record.get("bars_5m") or []:
        try:
            stamp, price = int(row[0]), float(row[1])
            if price > 0:
                result.append((stamp, price))
        except (TypeError, ValueError, IndexError):
            pass
    return sorted(result)


def near_price(bars, target, now_utc):
    if not target:
        return None
    target_ts = target.timestamp()
    now_ts = now_utc.timestamp()
    possible = [(abs(t - target_ts), t, p) for t, p in bars
                if abs(t - target_ts) <= QUOTE_TOLERANCE and t <= now_ts]
    if not possible:
        return None
    _, stamp, price = min(possible, key=lambda row: row[0])
    return {"price": round(price, 5),
            "quote_at": datetime.fromtimestamp(stamp, timezone.utc).isoformat()}


def reference_close(day_closes, published):
    if not published:
        return None
    ny = published.astimezone(NEW_YORK)
    # Dopo la chiusura regolare, e' lecito utilizzare il close dello stesso
    # giorno; in premarket o in sessione si usa la chiusura precedente.
    allow_same_day = (ny.hour, ny.minute) >= (16, 0)
    session_day = ny.date().isoformat()
    suitable = []
    for day, raw in (day_closes or []):
        if day < session_day or (allow_same_day and day == session_day):
            try:
                if float(raw) > 0:
                    suitable.append((day, float(raw)))
            except (TypeError, ValueError):
                pass
    return max(suitable)[1] if suitable else None


def percent(price, baseline):
    return round((float(price) / float(baseline) - 1) * 100, 2) if baseline and price else None


def load_history():
    if not DEST.exists():
        return {"version": 1, "updated_at": None, "events": []}
    try:
        obj = json.loads(DEST.read_text(encoding="utf-8"))
        if isinstance(obj.get("events"), list):
            return obj
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    raise RuntimeError("Archivio catalyst non leggibile: evitare sovrascritture che cancellino lo storico.")


def update_history(candidates, market, now_utc):
    doc = load_history()
    events = doc["events"]
    index = {e.get("id"): e for e in events if e.get("id")}
    changed = False
    now_utc = now_utc.astimezone(timezone.utc)

    for c in candidates:
        cid = c.get("id")
        if not cid or cid in index:
            continue
        published = to_utc(c.get("published_at"))
        if not published:
            continue
        # Un risultato della scansione viene archiviato anche se manca il
        # prezzo all'istante della notizia: restituiremo N/D e non zero.
        entry = {
            "id": cid, "ticker": c.get("ticker"),
            "company": c.get("company"), "category": c.get("category"),
            "headline": c.get("headline"), "source": c.get("source"),
            "url": c.get("url"), "catalyst_type": c.get("catalyst_type"),
            "published_at": published.isoformat(),
            "first_seen_at": now_utc.isoformat(),
            "estimated_impact_pct": c.get("estimated_impact_pct"),
            "confidence_score": c.get("confidence_score"),
            "verification_status": c.get("verification_status", "DA_VERIFICARE"),
            "pct_at_publication": None,
            "price_at_publication": None,
            "publication_quote_at": None,
            "pct_at_detection": c.get("current_change_pct"),
            "checkpoints": {str(h): None for h in HORIZONS},
        }
        events.append(entry)
        index[cid] = entry
        changed = True

    for e in events:
        t = e.get("ticker")
        record = market.get(t) or {}
        published = to_utc(e.get("published_at"))
        if not published:
            continue
        # I dati a 5 minuti non coprono periodi arbitrariamente lontani.
        # In caso di buchi storici si manterra' N/D, mai valori ipotetici.
        if (now_utc - published).days > MAX_HISTORY_AGE_DAYS:
            continue
        bars = from_bars(record)
        if e.get("price_at_publication") is None:
            at_news = near_price(bars, published, now_utc)
            if at_news:
                base = reference_close(record.get("day_closes"), published)
                e["price_at_publication"] = at_news["price"]
                e["publication_quote_at"] = at_news["quote_at"]
                e["pct_at_publication"] = percent(at_news["price"], base)
                changed = True
        anchor = e.get("price_at_publication")
        if not anchor:
            continue
        outcomes = e.setdefault("checkpoints", {})
        for hours in HORIZONS:
            key = str(hours)
            target = published + timedelta(hours=hours)
            if outcomes.get(key) is not None or now_utc < target:
                continue
            sample = near_price(bars, target, now_utc)
            if not sample:
                continue
            outcomes[key] = {
                "return_pct": percent(sample["price"], anchor),
                "price": sample["price"],
                "quote_at": sample["quote_at"],
            }
            changed = True

    # Non rimuovere le informazioni vecchie: archivio cumulativo.
    if changed:
        events.sort(key=lambda e: e.get("published_at") or "", reverse=True)
        doc["version"] = 1
        doc["updated_at"] = now_utc.isoformat()
        DEST.parent.mkdir(parents=True, exist_ok=True)
        DEST.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    return len(events), changed
