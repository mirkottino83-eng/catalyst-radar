# Catalyst Radar

## Android / Google Play (in preparazione)

Abbiamo aggiunto un **progetto Android nativo** nella cartella `android/` con target
**API 36**, un'interfaccia sicura con la dashboard GitHub Pages e la gestione
notifiche Firebase per **singolo telefono**. I servizi ntfy della PWA sono
indipendenti: i loro messaggi non sono comandati dall'interruttore Android.

- Prova APK su GitHub Actions: **Android Play Store readiness**
- AAB firmato (richiede credenziali e configurazione Firebase): **Build signed Android App Bundle for Google Play**
- Procedura completa: [docs/PLAY_STORE.md](docs/PLAY_STORE.md)
- Testo scheda Play: [docs/PLAY_LISTING_IT.md](docs/PLAY_LISTING_IT.md)
- Informativa pubblica **ancora in bozza**: [privacy.html](privacy.html)

**Importante:** in assenza di `google-services.json` l'APK di debug è utilizzabile
per provare la dashboard, ma il selettore delle notifiche Android mostra
Firebase non configurato e non può inviare push. Anche con build riuscita,
restano da completare configurazione Firebase, upload key, test reali,
licenze di redistribuzione dati, scheda privacy e account Google Play.
Non è ancora una release approvata né pubblicata nello Store.

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

## Always-on market scanning and per-device notification choice

The scanner is **always enabled** on GitHub Actions; the static dashboard contains **no stop or start button** and **no 5-minute countdown circle**. GitHub Actions requests a scan every 5 minutes, but does not guarantee precise timing or 24/7 real-time feeds.

Each installation of the web app has a slider labelled **Notifiche sul dispositivo**, stored only in its own browser storage. Switching it on requests browser notification permission when supported and enables local alerts for newly discovered high-quality news candidates and fresh positive tech-macro transitions **while that web app is open**. Switching it off stops those local app alerts. It cannot affect other users.

**Critical limitation of the current release:** Android notifications currently delivered by the *separate ntfy app* are independent of this web-app slider and still arrive when the browser app is closed. To mute the existing ntfy channel, open ntfy and mute its subscription. The original single GitHub `NTFY_TOPIC` secret is not distributed to other users. Do not expose that secret in website JavaScript or embed it in an Android package.

For a truly functional individual on/off switch that also works in the background for all future Play Store users, the Android application needs a **native Firebase Cloud Messaging integration** with per-device `subscribeToTopic` / `unsubscribeFromTopic`, or a secure web-push subscription and backend. See [Play Store readiness](docs/PLAY_STORE.md). That server-side/push integration is **not yet deployed**.

We removed the old GitHub-issue control workflow and `config/control.json` so a public app visitor cannot accidentally change the global monitor or the delivery state for everyone.

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
