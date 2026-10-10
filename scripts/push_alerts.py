"""Deduplicated, opt-in ntfy push for Catalyst Radar.

Only sends after NTFY_TOPIC has been set as a GitHub Actions secret.
State is saved in data/alert_state.json; never put private topics into git.
"""
import copy
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from signal_quality import quote_health, read_time

STATE_PATH = Path(__file__).resolve().parents[1] / "data" / "alert_state.json"
NY = ZoneInfo("America/New_York")
HOME = "https://mirkottino83-eng.github.io/catalyst-radar/"
TOPIC_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
REQUIRED_MACRO = ("^IXIC", "^SOX", "^VIX", "^TNX", "CL=F")

def utcnow():
    return datetime.now(timezone.utc)

def load_state():
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}

def save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")

def fresh_macro(macro, market, at):
    """Avoid weekend, premarket, postmarket and stale-index 'strong positive' alerts."""
    local = at.astimezone(NY)
    if local.weekday() >= 5 or not (9*60+30 <= local.hour*60+local.minute < 16*60):
        return False
    if any(not quote_health(market.get(t, {}).get("last_quote_at"), at, fresh_minutes=25)["is_recent"]
           for t in REQUIRED_MACRO):
        return False
    if macro.get("tech_bias") != "strong_positive":
        return False
    values = ("nasdaq_change_pct", "sox_change_pct", "vix_change_pct",
              "treasury_10y_change_bp", "wti_change_pct", "macro_score")
    if any(macro.get(k) is None for k in values):
        return False
    return (macro["macro_score"] >= 72
            and macro["nasdaq_change_pct"] >= 0.5
            and macro["sox_change_pct"] >= 0.5
            and macro["vix_change_pct"] <= 0
            and macro["treasury_10y_change_bp"] <= 4
            and macro["wti_change_pct"] <= 2
            and macro.get("geopolitical_risk_score", 35) <= 60)

def high_impact_headline(c, at):
    """Earlier but clearly flagged RSS lead; never claim a verified event or live move."""
    dt=read_time(c.get("published_at"))
    if dt is None or not (0 <= (at-dt).total_seconds()/60 <= 20):
        return False
    if c.get("verification_status") != "RSS_INDICIZZATO_DA_VERIFICARE":
        return False
    if c.get("satispay_status") == "unavailable":
        return False
    quality=c.get("factors") or {}
    if (quality.get("source_quality") or 0) < 85 or (quality.get("catalyst_strength") or 0) < 84:
        return False
    if c.get("catalyst_type") not in {
        "fda_approval","trial_success","ma","large_contract",
        "guidance_raise","earnings_beat"
    }:
        return False
    if c.get("quote_status")=="RECENT_UNOFFICIAL":
        move=c.get("current_change_pct")
        if move is not None and move > 8:
            return False
    return True

def eligible_candidate(c, at):
    # Permit high-impact indexed releases BEFORE the price moves, explicitly
    # unverified and without presenting stale quotes as current.
    if high_impact_headline(c, at):
        return True
    if c.get("verification_status") != "RSS_INDICIZZATO_DA_VERIFICARE":
        return False
    if c.get("quote_status") != "RECENT_UNOFFICIAL":
        return False
    published=read_time(c.get("published_at"))
    quoted=read_time(c.get("quote_at"))
    if not published or not quoted:
        return False
    age=(at-published).total_seconds()/60
    if not (0 <= age <= 45 and 0 <= (at-quoted).total_seconds()/60 <= 25):
        return False
    score=c.get("confidence_score")
    move=c.get("current_change_pct")
    hour=c.get("short_term_change_pct")
    rv=c.get("relative_volume")
    if any(v is None for v in (score,move,hour,rv)):
        return False
    if score < 78 or not (-2 <= move <= 8) or hour <= 0 or rv < 1.2:
        return False
    if c.get("satispay_status") == "unavailable":
        return False
    return True

def make_alerts(catalysts,macro,market,state,at=None):
    at=at or utcnow()
    pending=[]
    sent=state.get("sent", {})
    last_ticker=state.get("last_by_ticker", {})
    if not isinstance(sent,dict): sent={}
    if not isinstance(last_ticker,dict): last_ticker={}
    candidates=sorted(catalysts, key=lambda c:(c.get("early_signal") is True,
                                               c.get("confidence_score") or 0),reverse=True)
    for c in candidates:
        if len([p for p in pending if p["kind"]=="catalyst"])>=2:
            break
        if not eligible_candidate(c,at):
            continue
        if any(p.get("ticker")==c["ticker"] for p in pending):
            continue
        key=c.get("id") or c.get("ticker","")+"|"+c.get("headline","")
        if key in sent:
            continue
        recent=read_time(last_ticker.get(c["ticker"]))
        if recent and at-recent<timedelta(hours=2):
            continue
        direction=c.get("current_change_pct")
        rv=c.get("relative_volume")
        headline_only=high_impact_headline(c,at)
        label=("Notizia forte DA VERIFICARE" if headline_only else
               "Candidato precoce" if c.get("early_signal") else "Catalyst potenziale")
        move_label=(f"{direction:+.2f}%" if direction is not None
                    and c.get("quote_status")=="RECENT_UNOFFICIAL" else "N/D")
        volume_label=f"{rv:.2f}x" if rv is not None else "N/D"
        pending.append({
            "kind":"catalyst", "key":key, "ticker":c["ticker"],
            "title":f"Catalyst Radar · {c['ticker']} · {label}",
            "message":f"{c.get('headline','')[:220]}\nVariazione osservata {move_label} · RVOL 1h {volume_label} · qualità {c.get('confidence_score',0):.0f}/100.\nNEWS RSS NON VERIFICATA · controlla fonte originale e ora dell'evento.",
            "priority":"4", "tags":"chart_with_upwards_trend",
        })
    favourable=fresh_macro(macro,market,at)
    previous=bool(state.get("macro_favorable",False))
    cooldown_at=read_time(state.get("last_macro_sent"))
    if favourable and not previous and (cooldown_at is None or at-cooldown_at>=timedelta(hours=4)):
        pending.append({
            "kind":"macro", "key":"macro:strong_positive",
            "title":"Catalyst Radar · TECH MACRO MOLTO FAVOREVOLE",
            "message":f"Nasdaq {macro['nasdaq_change_pct']:+.2f}% · SOX {macro['sox_change_pct']:+.2f}% · VIX {macro['vix_change_pct']:+.2f}% · US10Y {macro['treasury_10y_change_bp']:+.1f} bp.\nIndicatori recenti e concordi, non garantiscono un rialzo.",
            "priority":"4", "tags":"chart_with_upwards_trend"
        })
    return pending, favourable

def publish(topic, alert, session=requests):
    response=session.post(
        f"https://ntfy.sh/{topic}",
        data=alert["message"].encode("utf-8"),
        headers={"Title":alert["title"], "Priority":alert["priority"],
                 "Tags":alert["tags"], "Click":HOME,
                 "Cache":"no"},
        timeout=12,
    )
    response.raise_for_status()

def run_alerts(catalysts,macro,market,at=None,publisher=publish):
    """Send only on successful transport; disable by default if no safe topic."""
    topic=os.getenv("NTFY_TOPIC","").strip()
    if not TOPIC_PATTERN.fullmatch(topic):
        print("ntfy disabled: set a random 16-64 char NTFY_TOPIC repository secret")
        return {"configured":False,"sent":0}
    at=at or utcnow()
    state=load_state()
    pending,favourable=make_alerts(catalysts,macro,market,state,at)
    state=copy.deepcopy(state)
    state.setdefault("sent",{})
    state.setdefault("last_by_ticker",{})
    cutoff=at-timedelta(days=2)
    state["sent"]={k:v for k,v in state["sent"].items()
                   if (t:=read_time(v)) and t>=cutoff}
    delivered=0
    delivered_macro=False
    macro_was_queued=any(p["kind"]=="macro" for p in pending)
    for alert in pending:
        try:
            publisher(topic,alert)
            delivered+=1
            if alert["kind"]=="macro":
                delivered_macro=True
            if alert["kind"]=="catalyst":
                state["sent"][alert["key"]]=at.isoformat()
                state["last_by_ticker"][alert["ticker"]]=at.isoformat()
            else:
                state["last_macro_sent"]=at.isoformat()
            # Save after every success to prevent duplicates on partial delivery.
            save_state(state)
        except requests.RequestException as exc:
            print(f"ntfy send failure ({alert['kind']}): {exc.__class__.__name__}")
        except Exception as exc:
            print(f"ntfy unexpected failure ({alert['kind']}): {exc.__class__.__name__}")
    # Retry unsent macro transition next run; never mark failed push as delivered.
    state["macro_favorable"]=(favourable and (not macro_was_queued or delivered_macro))
    state["updated_at"]=at.isoformat()
    save_state(state)
    print(f"ntfy configured; delivered {delivered} alert(s)")
    return {"configured":True,"sent":delivered}
