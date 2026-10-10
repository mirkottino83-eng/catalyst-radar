# Catalyst Radar — percorso verso Google Play Store

## Principio fondamentale

Lo scanner del mercato resta **uno solo** sul backend. I dispositivi dei singoli utenti scaricano lo stesso feed pubblico; nessun utente deve poter avviare, fermare o modificare il monitoraggio globale.

## Notifiche per ciascun telefono

### Versione PWA attuale
Il pulsante di notifica salva una preferenza **locale** nel dispositivo e controlla solo gli avvisi emessi dalla pagina quando è aperta e il browser concede il permesso. La sottoscrizione attuale ntfy rimane un servizio **esterno**, non gestibile via JavaScript in GitHub Pages. Non è corretto chiamarlo un interruttore delle push ntfy.

### Versione nativa Android da realizzare
1. Creare un progetto Firebase dedicato a Catalyst Radar e registrare l'app Android con un identificativo permanente.
2. Aggiungere l'SDK ufficiale Firebase Cloud Messaging (FCM) all'app Android. Richiedere `POST_NOTIFICATIONS` su Android 13+ soltanto quando l'utente attiva l'interruttore.
3. Implementare un gestore nativo della preferenza: **ON** = `FirebaseMessaging.subscribeToTopic("catalyst-alerts")` e/o `subscribeToTopic("tech-macro")`; **OFF** = `unsubscribeFromTopic(...)`. Attendere il completamento delle operazioni prima di confermare visivamente la modifica; gestire errori e riprovare.
4. Integrare un backend autenticato per inviare push tramite FCM agli argomenti, con una credenziale **server-side** mai inserita in app, repository pubblico o pagine GitHub. Il backend può usare lo scanner esistente come produttore degli eventi, ma GitHub Pages non è da solo un backend push.
5. Inserire un canale notifiche Android, aprire il catalyst corrispondente quando si tocca la notifica, usare priorità adeguate, deduplicare gli eventi e rispettare i permessi e le preferenze dei singoli dispositivi.
6. Consentire utenti multipli senza accesso a GitHub: nessun login GitHub, nessun topic ntfy condiviso, nessun secret sul client, nessuna operazione che cambia il monitoraggio comune.
7. Testare con almeno due telefoni: uno con interruttore OFF non riceve nulla, quello ON riceve gli avvisi, il backend continua a scansionare sempre, e il comportamento è corretto con app aperta, in background o chiusa.

## Pubblicazione e vincoli

- Un sito PWA installato oggi **non è automaticamente una pubblicazione sul Play Store**: servirà un pacchetto Android (per esempio un'app nativa, oppure wrapper/TWA con adeguata integrazione push).
- Preparare informativa privacy, dichiarazione Data safety, descrizione dei dati trattati e gestione dei permessi notifiche secondo i requisiti Google Play aggiornati al momento della pubblicazione.
- Verificare le condizioni d'uso e le licenze delle fonti finanziarie: dati accessibili gratuitamente per ricerca personale non sono necessariamente autorizzati alla redistribuzione a tutti gli utenti.
- Il servizio GitHub Actions programmato ogni cinque minuti è **best effort** e potrebbe non essere adatto a un'app pubblica con requisiti di tempestività e disponibilità.
- La schermata deve mostrare orari veri di scansione e delle singole quotazioni, senza usare diciture “tempo reale” dove la fonte non lo garantisce.

## Criterio di accettazione per la pubblicazione

Il comando "Notifiche" deve controllare effettivamente *la consegna delle push* al singolo utente, senza dipendere dall'app ntfy esterna e senza alterare le notifiche degli altri dispositivi. Fino a quel momento lo slider attuale è esplicitamente limitato agli avvisi locali della PWA aperta.
