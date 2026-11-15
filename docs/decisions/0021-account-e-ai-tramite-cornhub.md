# 0021 — Account unico e AI tramite cornhub

Languorino non ha più login, registrazione, password, chiavi AI né tetti di
spesa propri. L'account vive su **cornhub** (https://cornhub.it, repo
cornhub), che è un provider OpenID Connect e un gateway AI; il modello è
quello del template (templatino, ADR 0002 lì). Nel codice:
`backend/apps/core/cornhub.py` (client, identico in tutte le app),
`backend/apps/users/sso.py` (login), `backend/apps/ai/client.py` (adattatore
che tiene le firme di sempre), `frontend/src/components/AiCost.tsx`.

Sostituisce in parte ADR 0005, 0011, 0014, 0015 e 0020 (chiavi Gemini,
modelli, tetti giornalieri, codice di invito): quelle restano per la storia.

## Login

1. Il frontend senza sessione apre `/accedi`, che manda (al massimo una volta
   ogni 30 secondi, per non fare un giro infinito se qualcosa non va) a
   `/api/auth/sso/start?next=<percorso>`.
2. Il backend crea state, nonce e PKCE (S256) in un cookie firmato httpOnly
   (`languorino_refresh_sso_login`, 10 minuti, path `/api/auth/sso`) e
   rimanda a `CORNHUB_URL/o/authorize/`.
3. cornhub fa entrare (o registrare) e torna su `/api/auth/sso/callback`.
4. Il backend controlla lo state, scambia il codice sulla rete interna
   (`CORNHUB_INTERNAL_URL/o/token/`), verifica l'id_token (RS256, JWKS di
   cornhub, `iss`, `aud`, `exp`, `nonce`) e trova l'utente: per
   `cornhub_sub`, poi per email **solo se cornhub la dichiara verificata**
   (così gli account di prima si agganciano e tengono ricette, piani e
   profilo), altrimenti lo crea senza password. Nome, email e lingua si
   aggiornano a ogni login.
5. Da lì la sessione è quella di sempre (refresh nel cookie httpOnly
   `languorino_refresh`). A ogni refresh si chiede a cornhub lo stato
   dell'account (cache 2 minuti): spento o senza accesso all'app = sessione
   chiusa e refresh token in blacklist.
6. Logout: blacklist, poi il `logout_url` di cornhub.

La pagina Account tiene solo quello che è dell'app: indirizzo pubblico
`/u/<handle>`, lingua. Nome, email e password si vedono e rimandano a
cornhub (`/api/auth/config`). Il profilo alimentare (`Profile`, con nome e
cognome) resta dati dell'app. Per il passaggio:
`manage.py export_cornhub_users` stampa gli utenti (con l'hash della
password) da importare su cornhub.

## AI

Nessuna chiamata diretta a Gemini: `apps/ai/client.py` chiama
`cornhub.generate` / `cornhub.image` / `cornhub.live_token` con `user=` chi
ha chiesto (nei task Celery il proprietario del job, del ricettario o del
piano) e il nome della funzione nel listino di cornhub:

| Funzione | Livello | Dove |
|---|---|---|
| `meal_ideas` | piccola | `plans/swap.py` |
| `ask`, `ask_estimate` | piccola | `plans/ask.py` |
| `recipe_nutrition` | piccola | `recipes/nutrition.py` |
| `interview`, `interview_audio` (con la registrazione) | piccola | `profiles/interview.py` |
| `fridge_scan`, `cook_ideas` | piccola | `kitchen/cook_today.py` |
| `import_recipes` | grande | `recipes/importing.py` (job da foto e PDF) |
| `book_read` | grande | `recipes/tasks.py` → `read_recipes` (un pezzo di ricettario) |
| `book_photos` | grande | `recipes/book_images.py` |
| `recipe_image` | grande | `recipes/images.py` |
| `plan_week`, `plan_recipe` | grande | `plans/generation.py` |
| `nutritionist_plan` | grande | `plans/nutritionist.py` |
| `interview_live` | grande | `profiles/live.py` (token Gemini Live per il browser) |

Le piccole le paga la chiave di casa, dentro una quota giornaliera in
pannocchie; le grandi la chiave dell'utente, dentro i suoi limiti in euro.
Accanto al bottone di ogni funzione grande il frontend mostra `<AiCost>`
(chi paga e la stima, con `count` per le azioni da più chiamate: settimane
di piano, pezzi di ricettario, ricette da disegnare).

Errori, tradotti nelle eccezioni di sempre:

- `overloaded` → `AIOverloaded`: i lavori lunghi (ricettari, piano,
  illustrazioni) riprovano più tardi come prima;
- `needs_key`, `limit`, `house_empty` → `AIBudgetExceeded`: il lavoro si
  **ferma** con il messaggio di cornhub (prima un ricettario aspettava la
  mezzanotte: ora aspettare non basta, serve la chiave o un limite più alto).
  Le risposte con l'errore portano `account_url`, che il frontend mostra come
  link;
- il resto → `AIError`, il messaggio va all'utente così com'è.

Il registro `AiCall` e i tetti `AI_CALLS_PER_DAY*`, `AI_LIVE_SESSIONS_PER_DAY`
e `AI_IMAGES_PER_DAY` non ci sono più: chiamate e spese le conta cornhub.
Resta il limite orario `THROTTLE_AI` sulle view, contro le raffiche.

La voce in tempo reale resta dal browser a Gemini Live (`@google/genai` nel
frontend, ADR 0014): cambia solo chi crea il token monouso.

**Perché:** un account e una password per tutta la suite invece di una copia
del login per app; chiavi API in un solo posto, cifrate, che l'app non vede
mai; limiti di spesa veri, calcolati sui token dichiarati dai provider, al
posto del conteggio delle chiamate.

**Costo accettato:** cornhub è un punto unico: se è giù non si entra (le
sessioni aperte continuano) e l'AI si ferma. Il codice di invito
(`SIGNUP_CODE`) sparisce: chi entra lo decide cornhub con l'accesso all'app.

**Quando rivederla:** se Languorino deve funzionare da solo, fuori dalla suite.
