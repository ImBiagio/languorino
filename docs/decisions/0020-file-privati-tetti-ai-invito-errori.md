# 0020 — File privati fuori da `/media`, tetto giornaliero all'AI, codice di invito, errori a GlitchTip

Quattro scelte nate dalla revisione di sicurezza del 2026-11-14 (il numero
salta 0017–0019, presi dai branch delle feature non ancora unite).

- **File privati**: via `/media` si servono solo le immagini (ricette,
  avatar). `books/` (PDF dei ricettari) e `jobs/` (file dei lavori: piani del
  nutrizionista, foto del frigo, audio) rispondono sempre 404: lo fa Caddy in
  produzione (`deploy/Caddyfile`) e `apps/core/media.py` in sviluppo, sullo
  stesso elenco (`PRIVATE_MEDIA_PREFIXES`; un test controlla che non divergano).
  Nessuna view per scaricarli: nessun serializer ne espone l'URL e il frontend
  non li apre mai, li legge solo il backend dal disco.
- **Tetto all'AI** (`apps/ai/budget.py`): chiamate riuscite a Gemini al giorno
  contate in `AiCall`, per utente (`AI_CALLS_PER_DAY`, 400) e per tutta l'app
  (`AI_CALLS_PER_DAY_GLOBAL`, 2000), più le conversazioni a voce per utente
  (`AI_LIVE_SESSIONS_PER_DAY`, 20). Si chiude in due punti: il throttle
  `AiBudgetThrottle` sulle view con `throttle_scope = "ai"` (429 con il
  messaggio in `detail`) e `check_budget` dentro `generate`,
  `generate_image` e `live_token`, che ferma anche i lavori già in coda
  (`AIBudgetExceeded`, il job o il ricettario si ferma con quel messaggio).
- **Codice di invito**: con `SIGNUP_CODE` impostato `POST /api/auth/register`
  vuole `invite_code` (confronto a tempo costante, controllato prima di ogni
  altro campo); `GET /api/auth/config` dice al frontend se mostrare il campo.
  Vuoto = registrazione aperta, come prima.
- **Errori**: `sentry-sdk` verso GlitchTip (`config/sentry.py`), acceso solo
  con `SENTRY_DSN`, da `dev.py` e `prod.py` e mai dai settings dei test.
  Integrazioni Django e Celery, `send_default_pii=False`,
  `traces_sample_rate=0`, niente corpo delle richieste né variabili locali.

**Perché:**
- Un UUID nell'URL non è un controllo d'accesso: i piani del nutrizionista sono
  dati sulla salute e l'URL finisce in log, cronologia e backup. Una view
  autenticata per scaricarli è stata scartata perché oggi nessuno li scarica:
  meno codice, meno superficie.
- Il limite orario lascia a un account 60 richieste l'ora per sempre, e una
  richiesta può far partire decine di chiamate in Celery. Contare le chiamate
  vere, dove partono, è l'unico tetto che vale anche per i lavori lunghi. Solo
  quelle riuscite, come per le immagini: un 503 di Gemini non costa.
- Il codice di invito è lo schema già usato su cinemino: chiude la
  registrazione senza togliere la pagina né gestire inviti uno per uno.
- Un errore in un task Celery oggi si vede solo leggendo i log del server.
  Corpo delle richieste e variabili locali restano fuori perché contengono
  profilo, piano del nutrizionista e testo delle interviste.

**Costo accettato:**
- I file privati non si possono riscaricare dall'app (nemmeno dal proprio
  proprietario) e il link nell'admin Django per i file dei lavori dà 404.
- Un giorno molto pesante (più ricettari lunghi insieme) può toccare il tetto:
  il lavoro si ferma con un messaggio e va ripreso a mano il giorno dopo. Ogni
  chiamata a Gemini fa una `COUNT` in più su `AiCall`.
- Il codice di invito è uno solo, condiviso: per toglierlo a qualcuno va
  cambiato per tutti.
- Senza variabili locali gli errori su GlitchTip sono più poveri: per capire
  servono anche i log.

**Quando rivederla:**
- Se serve far riscaricare un PDF o un piano: view autenticata con controllo
  del proprietario e `FileResponse`, non riaprire `/media`.
- Se gli utenti crescono: tetti per piano d'uso o in token/costo invece che in
  numero di chiamate; inviti personali al posto del codice unico.
