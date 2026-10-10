# Catalyst Radar

Web app/PWA for **research and monitoring**, not a trading broker. Runs as a static dashboard; a Python scanner updates `data/latest.json` through GitHub Actions. No Replit required.

## What the free scanner does

- **Catalyst candidates:** finds fresh indexed headlines via Google News RSS, filters promotional/old recycled headlines and labels every RSS candidate as **unverified** until its underlying event is independently confirmed.
- **SEC documents:** reads recent official SEC submissions when available. Uses an actual acceptance timestamp, never an invented 12:00 release time. A filing alone is **not** a buy signal.
- **Intraday mover scanner:** observes 1-hour price movement and, when data permits, the same-hour relative volume compared with the previous NY trading session.
- **Early filters:** highlights stocks still at or below +1.5% day movement *only* if data is recent, positive 1-hour momentum is observed, volume comparison is available and the news was recently indexed.
- **Quality rather than probability:** score 0–100 is an explanatory ranking, **not a statistical chance** of a rise. Indicative impact is omitted if quote, 1-hour price or volume are unavailable/stale.
- **TradingView:** opens an embedded/free chart to verify observations manually. Chart feed real-time access depends on TradingView/exchange.

## Data and important limitations

- Market prices come from unofficial Yahoo Finance endpoints via `yfinance`. Coverage/latency vary; no licensed tick-by-tick feed. On market closures, observations are stale and the momentum list can be empty.
- Google News RSS is an *index*, not licensed Benzinga/Reuters breaking news. The RSS publication timestamp is **not** proof of when a corporate event took place.
- A relative volume number is computed only where comparable 5-minute bars exist for the same NY-clock 1-hour window of the previous session. Otherwise it shows **N/D**, not an assumed 1.0x.
- U.S. market holidays, GitHub scheduler delays, Yahoo API restrictions and SEC rate limits can cause missing or stale results.
- The GitHub Actions schedule requests a scan **every 5 minutes** (minute 2, 7, 12, etc., UTC). The actual execution can be delayed, skipped or unavailable; this is not a continuous, tick-by-tick feed. The phone auto-refreshes displayed data every minute while the app is open. No local countdown is needed.
- Adding a local watchlist symbol filters visible results, but does not add it to the cloud scan universe.
- Availability on Satispay is marked 'check' unless independently confirmed.
- No paid service accounts or proprietary Benzinga/Finviz/TradingView feeds are used.

## Remote controls (server-wide and authenticated)

The PWA has **three visible commands**: enable monitoring 24/7 (best-effort every 5m), disable monitoring, and toggle ntfy notifications independently. The switches apply to the **GitHub cloud backend**, not just local browser refresh.

For security, GitHub Pages cannot directly modify a private GitHub Actions workflow without authenticating. Each button opens a **pre-filled GitHub issue**. Sign into the owning GitHub account and press **Submit new issue** to confirm the action. The owner-only GitHub Actions workflow `.github/workflows/radar-controls.yml` checks the issue author and exact issue title, edits `config/control.json`, pushes the public boolean state, and closes the request. Other users cannot change these settings. The app reads the public state file on reload or every minute; the update may take a few minutes to propagate through GitHub Pages.

- **Monitoring OFF:** scheduled jobs still wake briefly every 5 minutes to read the setting, but skip market/news scans and ntfy delivery. The latest dashboard is marked paused; history is retained. This is not disabling the GitHub cron itself.
- **Monitoring ON:** the next scheduled or push-triggered run resumes actual scanning.
- **Notifications OFF:** market scans keep running, but no new ntfy messages are sent. Your ntfy subscription remains in place.
- **Notifications ON:** ntfy sending resumes (provided the secret `NTFY_TOPIC` was configured). It does not send missed alerts retroactively.
- This method needs no PAT/password stored in your PWA and no paid hosting. Control requests are visible as closed issues in the public repository, and they contain *no secrets*.

## Development and tests

Python 3.12, `pip install -r requirements.txt`, `python scripts/scanner.py`. The scanner requires internet and may fail to fetch some free sources. Run local tests without network using `python -m unittest discover -s tests -v`. The `quality-check.yml` GitHub workflow checks syntax and tests on pull requests.

## Android alerts (free ntfy, explicit opt-in)

The Android phone needs the independent **ntfy** app. Push still arrives with Catalyst Radar closed, *only after* the private topic is connected to GitHub.

1. Install [ntfy for Android](https://ntfy.sh/) (Google Play or F-Droid).
2. Generate a **long random topic** (16–64 characters, letters/numbers/underscore/hyphen; prefer 30+ random characters). In ntfy choose **Subscribe to topic** and enter it. Leave ntfy notifications enabled in Android.
3. Visit repository **Settings → Secrets and variables → Actions → New repository secret**. Name: `NTFY_TOPIC`, value: **exactly the same random topic**. Do not enter the value into a tracked file, issue, commit, screenshot, or chat.
4. In GitHub **Actions → Update Catalyst Radar → Run workflow** (or let the next scheduled run start). Verify `data/latest.json` shows `"push_configured": true`. This only proves the sender is configured, not that the phone subscribed.
5. When a qualifying *new* signal appears, Android receives the notification. No alerts at the weekend solely on stale macro quotes. If desired, set ntfy notification sound to **silent/no vibration** in Android settings.

Security: free/public ntfy topic names are unprotected subscriptions; anyone who guesses the topic can read/send messages. Use an unpredictable topic and share it with no one. A paid or self-hosted authenticated server would offer stronger access control.

### When push is sent

- **Potential catalysts:** (A) high-impact indexed releases from recognized financial news/wire sources within 20 minutes **even before a price reaction**, always explicitly flagged *UNVERIFIED*, or (B) high-scoring RSS candidates within 45 minutes with recent price, positive 1-hour momentum, same-clock relative volume >= 1.2x and move <= +8%. Maximum two per scan; deduplicated per news ID and per ticker over 2 hours. No fake price is shown when data is missing. These are leads for verification, not trade instructions.
- **Very favourable tech macro:** only with recent Nasdaq, SOX, VIX, Treasury and WTI quotes during the NY cash market session. Requires strong-positive technical score and corroborating index, VIX, yield, oil and geopolitical filters. Alerts only on a transition to favourable conditions with 4h cooldown.
- Persistence: alert IDs and macro state stored in `data/alert_state.json`; the **topic secret is never written** to the repository or results. Failed sends do not count as delivered.

No notifications can arrive until `NTFY_TOPIC` is configured. GitHub Actions, free quote feeds and ntfy free delivery have no hard latency guarantee. The ntfy.sh free tier has rate limits (including a published default 250 messages/day).

For informational research only; not personalized financial advice.
