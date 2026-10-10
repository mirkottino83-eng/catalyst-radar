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
- The GitHub Actions schedule is **best effort every 15 minutes**, not guaranteed continuous background execution. The phone's local 25-minute monitor does not launch a new cloud scan.
- Adding a local watchlist symbol filters visible results, but does not add it to the cloud scan universe.
- Availability on Satispay is marked 'check' unless independently confirmed.
- No paid service accounts or proprietary Benzinga/Finviz/TradingView feeds are used.

## Development and tests

Python 3.12, `pip install -r requirements.txt`, `python scripts/scanner.py`. The scanner requires internet and may fail to fetch some free sources. Run local tests without network using `python -m unittest discover -s tests -v`. The `quality-check.yml` GitHub workflow checks syntax and tests on pull requests.

## Alerts

No new push subscriptions are configured by this change. Browser notifications only work under browser permission and foreground activity. An optional `NTFY_TOPIC` environment variable can send updates, but it must be intentionally configured and secured by the user. Do not expose private topics or API keys in this public repository.

For informational research only; not personalized financial advice.
