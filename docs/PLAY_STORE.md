# Guida operativa per Google Play – Catalyst Radar (Android)

## Stato attuale

Sono stati aggiunti un progetto Android nativo in `android/`, una build APK di test GitHub Actions,
un workflow di bundle AAB firmato e l'integrazione FCM con selettore notifiche per singolo
dispositivo. **Non è ancora pubblicato su Google Play e non è ancora pronto per la produzione
finché non vengono soddisfatti i prerequisiti e verificati i test reali.**

La PWA già installata sul telefono funziona separatamente e continua a usare la
sottoscrizione esterna ntfy. Il selettore PWA non può interrompere le notifiche ntfy;
l'app Android nativa si basa invece sul proprio selettore Firebase.

## Versioni e identificativo

- Package Android provvisorio: `com.mirkottino83.catalystradar`.
  **Confermare l'identificativo prima** di registrarlo su Firebase/Google Play:
  dopo la prima pubblicazione non va cambiato.
- Android 16, `targetSdk=36`, `compileSdk=36`, `minSdk=26`.
- Gradle 8.13, Android Gradle Plugin 8.13.2, JDK 17.
- Versione iniziale 1.0.0, `versionCode=1`. Per ogni upload successivo incrementare `versionCode`.

## 1. APK di prova senza account a pagamento

In GitHub vai su **Actions → Android Play Store readiness → Run workflow**.
Il test genera un APK `catalyst-radar-android-debug` scaricabile nella sezione
**Artifacts** dell'esecuzione. In questo APK le notifiche Firebase sono
volutamente **non disponibili** in assenza di `google-services.json`, ma il
sito, i grafici e la watchlist possono essere controllati su Android.
Si può anche aprire la cartella `android/` in Android Studio e premere Run.

Nota: l'APK di debug non è un AAB firmato per Google Play.

## 2. Firebase, una volta sola (indispensabile per notifiche native)

1. Accedi a `https://console.firebase.google.com/` con un tuo account.
2. Crea un progetto Firebase. Aggiungi un'app **Android** usando lo stesso
   package `com.mirkottino83.catalystradar`.
3. Scarica il suo `google-services.json`: contiene la configurazione pubblica del client,
   non una chiave del service account. Per privacy operativa non inserirlo nel
   repository pubblico: caricalo come segreto GitHub `FIREBASE_GOOGLE_SERVICES_JSON_B64`,
   con contenuto del file codificato in base64.
4. In Firebase/Google Cloud abilita l'API Firebase Cloud Messaging.
   Per inviare dal backend crea un **service account** con il permesso minimo
   per FCM (es. Firebase Cloud Messaging API Admin sul progetto di destinazione,
   da verificare nel progetto). Scarica la chiave JSON **solo sul tuo computer**,
   codificala in base64 e salvala come GitHub Actions secret
   `FIREBASE_SERVICE_ACCOUNT_JSON_B64`. Non pubblicarla, non mandarla in chat.
5. Il modulo `scripts/fcm_push.py`, già collegato a `scripts/scanner.py`,
   invia **soltanto dopo** che questo secret è configurato. Usa topic FCM
   `catalyst-alerts` e `tech-macro`, separati dal topic privato ntfy.
6. L'app nativa chiede `POST_NOTIFICATIONS` solo quando l'utente attiva il cursore.
   Quando lo disattiva si cancella dai due topic e blocca localmente ogni avviso.

## 3. Firma per caricamento Play

1. Genera una chiave di **upload** da Android Studio (`Build > Generate Signed Bundle / APK`)
   oppure da un computer fidato con `keytool`; **conserva l'originale in luogo sicuro**.
2. Aggiungi questi GitHub Actions secrets al repository:
   - `ANDROID_UPLOAD_KEYSTORE_B64`: contenuto base64 del file `.jks`
   - `ANDROID_KEYSTORE_PASSWORD`
   - `ANDROID_KEY_ALIAS`
   - `ANDROID_KEY_PASSWORD`
   - `FIREBASE_GOOGLE_SERVICES_JSON_B64` (dal punto precedente)
3. Apri **Actions → Build signed Android App Bundle for Google Play → Run workflow**.
   Se manca una credenziale il job termina senza produrre AAB.
4. Scarica l'artefatto privato `catalyst-radar-play-signed-aab`.
   Non diffondere chiavi o file `.jks` insieme al bundle.

## 4. Pubblicazione in Play Console

1. Apri un account su `https://play.google.com/console`, verifica l'identità
   e paga la quota unica di registrazione, attualmente 25 USD.
2. Crea l'app, scegli l'identificativo stabile, carica l'AAB firmato e configura
   **Play App Signing**.
3. Inserisci le informazioni dell'app, screenshot reali, icona, feature graphic
   e le descrizioni in `docs/PLAY_LISTING_IT.md`.
4. Finalizza `privacy.html` con l'identità del titolare e un contatto email
   funzionante prima di usarla in una scheda pubblica. Completa il modulo
   **Sicurezza dei dati** per tutte le SDK e i dati effettivamente trattati.
5. Compila la dichiarazione **Funzionalità finanziarie**. L'app mostra notizie,
   ranking e dati borsistici, ma non esegue ordini, non contiene servizi di
   brokeraggio e non promette investimenti garantiti. Dichiarare soltanto le
   categorie realmente pertinenti, dopo avere letto il questionario di Play.
6. Per i nuovi account personali creati dopo il 13 novembre 2023 possono
   essere richiesti almeno **12 tester in un test chiuso per 14 giorni consecutivi**
   prima di richiedere la pubblicazione a tutti.
7. Prova l'app su almeno due Android distinti con notifiche ON/OFF,
   app aperta, in background e chiusa, e controlla la consegna di veri alert
   e la corretta gestione delle notifiche duplicate.

## Blocchi ancora da risolvere prima della release pubblica

- **Licenze dati**: `yfinance`/Yahoo e articoli RSS possono avere condizioni
  che non consentono redistribuzione commerciale/pubblica. Verificare i diritti,
  acquistare feed se obbligatorio oppure limitare/rimuovere contenuti non autorizzati.
- **Affidabilità dello scanner**: il cron gratuito GitHub Actions ogni 5 minuti
  è best-effort, senza SLA. Non promettere feed realtime o consegna immediata.
- **Firebase**: finché non sono stati inseriti i due secret del progetto Firebase,
  le notifiche native non funzionano e devono apparire come non configurate.
- **Policy Google Play**: verifica privacy, dichiarazioni finanziarie, contenuti
  promozionali, accuratezza delle descrizioni, support email, screenshot reali.
- **Qualità app nativa**: test sicurezza WebView, collegamenti a fonti,
  apertura dei grafici e comportamento offline prima di presentare la release.
- **Firma e test**: testare una reale build AAB firmata e un percorso Play Console
  internal/closed test. I test GitHub non sostituiscono la verifica su dispositivi.

Fonti da aggiornare al momento della pubblicazione:
- https://developer.android.com/google/play/requirements/target-sdk
- https://developer.android.com/guide/app-bundle/faq
- https://support.google.com/googleplay/android-developer/answer/14151465
- https://support.google.com/googleplay/android-developer/answer/10787469
- https://support.google.com/googleplay/android-developer/answer/13849271
- https://firebase.google.com/docs/cloud-messaging/android/client
