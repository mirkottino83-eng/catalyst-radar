"""Quality controls for free-data Catalyst Radar signals.

All timestamps are observation times, not proof of the underlying event time.
Missing quotes and volumes remain missing: do not convert them to zero.
"""
import re
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
LOW_VALUE = (
    r"\b(?:sponsorship|sponsors?|sponsored|philanthrop\w*|charity|donation|"
    r"donates?|scholarship|community event|volunteer program)\b",
    r"\b(?:previously announced|last (?:week|month|year)|earlier this (?:week|month)|"
    r"a look back|news recap|explainer|explained|recap of)\b",
    r"\b(?:should you buy|stock prediction|price prediction|"
    r"what investors need to know|opinion|editorial|sponsored content)\b",
    r"\b(?:why .* stock (?:is|was) (?:up|down|rising|falling)|"
    r"what happened to .* stock)\b",
)

def read_time(value):
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc)

def headline_status(title, published, checked_at=None, max_age_hours=6):
    current = read_time(checked_at) or datetime.now(timezone.utc)
    dt = read_time(published)
    if dt is None:
        return "TIMESTAMP_NOT_VERIFIED"
    if dt > current + timedelta(minutes=5):
        return "FUTURE_TIMESTAMP"
    if current - dt > timedelta(hours=max_age_hours):
        return "OLD_NEWS"
    if any(re.search(pattern, title or "", re.I) for pattern in LOW_VALUE):
        return "SECONDARY_OR_NON_FINANCIAL"
    return "NEW_RSS_UNVERIFIED"

def quote_health(quote_time, checked_at=None, fresh_minutes=20):
    current = read_time(checked_at) or datetime.now(timezone.utc)
    quote = read_time(quote_time)
    if quote is None or quote > current + timedelta(minutes=5):
        return {"status": "UNAVAILABLE", "age_minutes": None, "is_recent": False}
    age = max(0.0, (current - quote).total_seconds() / 60)
    return {
        "status": "RECENT_UNOFFICIAL" if age <= fresh_minutes else "STALE",
        "age_minutes": round(age, 1),
        "is_recent": age <= fresh_minutes,
    }

def _clean_bars(bars):
    clean = []
    for row in bars or []:
        if not isinstance(row, (tuple, list)) or len(row) < 2:
            continue
        try:
            ts, price = int(row[0]), float(row[1])
        except (ValueError, TypeError):
            continue
        if price > 0 and abs(ts) > 1000000000:
            clean.append((ts, price))
    return sorted(set(clean))

def hourly_change(bars):
    """Only compare observations about 60 minutes apart in the SAME NY day."""
    obs = _clean_bars(bars)
    if len(obs) < 2:
        return None
    latest_ts, price = obs[-1]
    local_day = datetime.fromtimestamp(latest_ts, NY).date()
    matches = [
        (abs((latest_ts - ts) - 3600), reference)
        for ts, reference in obs[:-1]
        if 3300 <= latest_ts - ts <= 4200
        and datetime.fromtimestamp(ts, NY).date() == local_day
    ]
    if not matches:
        return None
    reference = min(matches)[1]
    return round((price / reference - 1) * 100, 3)

def hourly_relative_volume(volume_bars):
    """Compare trailing hour with same NY clock window of a prior session.

    Requires actual observed 5-minute bars on both days. If no comparable
    session exists (weekends, missing data, first hour), report N/D.
    """
    clean = []
    for row in volume_bars or []:
        if not isinstance(row, (tuple, list)) or len(row) < 2:
            continue
        try:
            ts, vol = int(row[0]), float(row[1])
        except (ValueError, TypeError):
            continue
        if ts > 1000000000 and vol >= 0:
            clean.append((ts, vol))
    clean.sort()
    if not clean:
        return None
    last_ts = clean[-1][0]
    last_local = datetime.fromtimestamp(last_ts, NY)
    minute_end = last_local.hour * 60 + last_local.minute
    current_date = last_local.date()
    previous_dates = sorted({
        datetime.fromtimestamp(ts, NY).date() for ts, _ in clean
        if datetime.fromtimestamp(ts, NY).date() < current_date
    })
    if not previous_dates:
        return None
    prior_date = previous_dates[-1]
    def sample(day):
        result = []
        for ts, vol in clean:
            dt = datetime.fromtimestamp(ts, NY)
            mins = dt.hour * 60 + dt.minute
            if dt.date() == day and minute_end - 60 <= mins <= minute_end:
                result.append(vol)
        return result
    recent, previous = sample(current_date), sample(prior_date)
    if len(recent) < 6 or len(previous) < 6:
        return None
    prior_sum = sum(previous)
    if prior_sum <= 0:
        return None
    return round(sum(recent) / prior_sum, 2)

def early_signal(age_minutes, move, hour_move, relative_volume, quote_recent):
    """Early observation, NOT a prediction or an automatic buy signal."""
    return (
        quote_recent is True
        and age_minutes is not None and 0 <= age_minutes <= 30
        and move is not None and -2 <= move <= 1.5
        and hour_move is not None and hour_move > 0
        and relative_volume is not None and relative_volume >= 1.2
    )
