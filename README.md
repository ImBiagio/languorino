# Languorino

Cosa mangio questa settimana? Languorino parte dal profilo (gusti, allergie,
obiettivi, stile di vita, anche raccontati a voce in un'intervista), genera il piano alimentare con il meal prep (anche seguendo quello del
nutrizionista), tiene
il ricettario di casa (anche dalle foto delle ricette scritte a mano),
calcola la spesa e, dalla foto del frigo, dice cosa cucinare oggi. Cosa fa in [docs/specifica.md](docs/specifica.md), come è
progettata in [docs/progettazione.md](docs/progettazione.md).

Stack: Django + DRF + Postgres + Celery/Redis + React (Vite, TypeScript) +
Tailwind con token Material 3, tutto in Docker Compose
([ADR 0001](docs/decisions/0001-stack.md)).

---

## Avvio

```bash
cp .env.example .env && docker compose up --build
```

| | |
|---|---|
| App | http://localhost:5177 |
| API | http://localhost:8030/api |
| Docs OpenAPI | http://localhost:8030/api/docs/ |
| Admin Django | http://localhost:8030/admin/ |

Le porte sono diverse dagli altri progetti per farli girare insieme; per lo
stesso motivo il cookie di refresh si chiama `languorino_refresh`.

Con `.env.example` la verifica email è disattivata (`REQUIRE_EMAIL_VERIFICATION=0`):
ci si registra ed entra subito. Le mail finiscono nei log del worker:
`docker compose logs -f worker`. Il codice è montato come volume (hot reload);
dopo nuove dipendenze ricostruisci l'immagine: `docker compose build backend`.

---

## Fondamenta

- **Auth JWT ibrida**: access token (15 min) in memoria, refresh (14 giorni) in
  cookie `httpOnly` su `/api/auth`, blacklist a logout e cambio password, un
  solo refresh in volo nel client (`frontend/src/lib/api.ts`). Registrazione,
  conferma email, reset password, cambio password. Rate limit su
  login/registrazione (`THROTTLE_AUTH`) e sulle chiamate all'LLM (`THROTTLE_AI`).
- **Mail** dal worker Celery dopo il commit, con retry, testo + HTML su un solo
  layout (`backend/templates/emails/`). In produzione SMTP di **Brevo**, lo
  stesso account di tutti i progetti (mittente `messagg@inoo.it`).
- **Soft delete + audit**: `BaseModel` (UUID, `deleted_at`) e `django-simple-history`.
- **Material 3**: ruoli M3 mappati in Tailwind, Roboto Flex, Roboto Mono per i
  numeri, Material Symbols Rounded. Rail su desktop, bottom bar e FAB sotto i
  768px, dialog di conferma M3 (`useConfirm()`), niente `window.confirm`.
  La palette va rigenerata dal colore seed del progetto (`frontend/src/index.css`).
- **i18n**: italiano sorgente, inglese in `backend/locale/en/LC_MESSAGES/`,
  frontend e backend sullo stesso catalogo gettext. Il nome dell'app sta in
  `settings.APP_NAME`, fuori dalle stringhe tradotte.
- **LLM** ([ADR 0005](docs/decisions/0005-llm-e-lavori-lunghi.md)): chiave Gemini in `GEMINI_API_KEY`
  (vuota = funzioni spente), modello in `GEMINI_MODEL` e riserve in `GEMINI_FALLBACK_MODELS`.
  Le chiamate girano sulla coda Celery `ai` (servizio `worker-ai`); log con
  `docker compose logs -f worker-ai`.

---

## Struttura

```
backend/
├── config/settings/     base · dev · prod · test
├── templates/emails/    layout unico delle mail
└── apps/
    ├── core/            BaseModel, methods (token, hash, mail), i18n, task mail
    ├── users/           User custom + auth JWT + mail dell'account
    ├── profiles/        profilo alimentare, gusti e allergie (14 allergeni UE), intervista (interview.py)
    ├── recipes/         ricette, tag, catalogo ingredienti (catalog.py), riconoscimento dei nomi, immagini (images.py),
    │                    import da foto (importing.py), ricettari PDF letti a pezzi (books.py, tasks.py), condivisione (sharing.py)
    ├── ai/              client Gemini unico (riserve, retry, registro AiCall)
    ├── jobs/            lavori lunghi su Celery (coda "ai"): file, stato, bozza, conferma
    ├── plans/           piano alimentare: calendario del prep (schedule.py), generazione a settimane (generation.py),
    │                    piano del nutrizionista letto da PDF/foto (nutritionist.py)
    ├── shopping/        lista della spesa: somme e conversioni dal piano (aggregate.py), ricalcolo
    └── kitchen/         cosa cucino oggi: foto del frigo, ricette che si possono fare, idee nuove (cook_today.py), pulizia delle idee mai salvate
frontend/src/
├── api/hooks.ts         hook TanStack Query, una sezione per area
├── lib/                 client HTTP, auth, i18n, format, tipi
├── components/          UI M3, layout, dialog di conferma
└── features/            auth · account · home · onboarding · profile · interview · recipes · plans · shopping · kitchen
deploy/                  compose di produzione, Caddy interno, edge condiviso
docs/decisions/          ADR (modello in 0000-modello.md)
```

### API

| | |
|---|---|
| `POST /api/auth/register` · `login` · `refresh` · `logout` | account e sessione (refresh nel cookie) |
| `POST /api/auth/verify-email/{token}` · `verify-email/resend` | conferma dell'indirizzo |
| `POST /api/auth/password` · `password-reset` · `password-reset/confirm` | cambio e reset della password |
| `GET/PATCH /api/me` | account (nome visibile, lingua) |
| `GET/PATCH /api/profile` · `POST /api/profile/complete` | profilo alimentare e fine del wizard |
| `GET/POST /api/profile/preferences` · `DELETE …/{id}` | gusti, antipatie, allergie, intolleranze |
| `POST /api/profile/interview` (JSON o multipart `messages`, `audio`) | un turno dell'intervista, anche a voce: job con risposta e proposte da confermare ([ADR 0013](docs/decisions/0013-intervista-e-voce.md)) |
| `GET /api/ingredients?q=` | suggerimenti dal catalogo (e dagli ingredienti propri) |
| `GET/POST /api/recipes` (`?q=`, `?tag=`, `?slot=`, `?max_minutes=`, `?difficulty=`, `?in_cookbook=`) · `GET/PATCH/DELETE …/{id}` | ricettario, con allergeni e avvisi dal profilo |
| `GET /api/tags` · `DELETE /api/tags/{id}` | tag con il numero di ricette |
| `GET/POST /api/jobs` (multipart `kind`, `files`) · `GET/DELETE /api/jobs/{id}` | lavori lunghi: import di ricette da foto e PDF |
| `POST /api/jobs/{id}/retry` · `POST /api/jobs/{id}/confirm` `{recipes}` | riprova un lavoro non riuscito · le bozze riviste diventano ricette |
| `GET/POST /api/recipe-books` (multipart `file`) · `GET/PATCH/DELETE …/{id}` · `POST …/{id}/retry` | ricettari PDF letti a pezzi ([ADR 0006](docs/decisions/0006-ricettari-pdf.md)); le ricette con `GET /api/recipes?book={id}` |
| `POST/DELETE /api/recipes/{id}/image` (multipart `file`) · `POST …/image/draw` | foto vera della ricetta o disegno di Gemini in un job ([ADR 0011](docs/decisions/0011-immagini-delle-ricette.md)) |
| `POST/DELETE /api/recipes/{id}/share` · `GET /api/shared/recipes/{token}` · `POST …/copy` | link di condivisione `/r/<token>`, pagina pubblica senza login, copia nel proprio ricettario ([ADR 0012](docs/decisions/0012-condivisione-delle-ricette.md)) |
| `POST /api/recipes/{id}/save` | una ricetta di un ricettario PDF, del piano o di "cosa cucino oggi" entra nel proprio ricettario |
| `GET/POST /api/plans` · `GET /api/plans/current` · `GET/DELETE /api/plans/{id}` | piano alimentare ([ADR 0007](docs/decisions/0007-piano-alimentare.md)): si genera una settimana alla volta |
| `POST /api/plans/{id}/activate` · `regenerate` · `retry` · `PATCH …/meals/{meal_id}` | attiva, rifai, riprendi, cambia un pasto |
| `GET/POST /api/nutritionist-plans` (multipart `files`) · `GET/PATCH/DELETE …/{id}` · `POST …/{id}/confirm` | piano del nutrizionista: lettura in un job, revisione, conferma ([ADR 0010](docs/decisions/0010-piano-del-nutrizionista.md)); si usa con `nutritionist_plan` in `POST /api/plans` |
| `GET/POST /api/shopping` · `GET/PATCH/DELETE …/{id}` · `POST …/{id}/regenerate` | liste della spesa dal piano o a mano ([ADR 0008](docs/decisions/0008-lista-della-spesa.md)) |
| `POST /api/shopping/{id}/items` · `PATCH/DELETE …/items/{item_id}` | voci a mano, spunta, "ce l'ho già", modifica |
| `POST /api/cook-today/scan` (multipart `files`) | foto del frigo → job con gli alimenti riconosciuti ([ADR 0009](docs/decisions/0009-cosa-cucino-oggi.md)) |
| `POST /api/cook-today/suggest` | ricette che si possono fare con quegli ingredienti e job con due idee nuove |
| `GET /api/i18n/catalog` · `POST /api/i18n/language` | traduzioni del frontend e lingua scelta |
| `GET /api/health` | healthcheck del container |

---

## Comandi

```bash
docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test backend pytest
```

```bash
docker compose run --rm --no-deps backend ruff check apps config
```

```bash
docker compose run --rm --no-deps frontend sh -c "npx tsc -b && npx eslint src --ext .ts,.tsx"
```

```bash
docker compose run --rm --no-deps backend python manage.py createsuperuser
```

Dopo una modifica a `backend/apps/recipes/catalog.py`:

```bash
docker compose exec backend python manage.py load_catalog
```

Traduzioni: estrai, traduci in `backend/locale/en/LC_MESSAGES/*.po`, ricompila
e committa `.po` e `.mo`.

```bash
docker compose run --rm --no-deps backend python manage.py makemessages -l en -i staticfiles --no-obsolete
```

```bash
docker compose run --rm --no-deps frontend npm run i18n:js
```

```bash
docker compose run --rm --no-deps -v "$PWD/frontend/.i18n:/i18n:ro" -w /i18n backend python /app/manage.py makemessages -d djangojs -l en -e js --no-location --no-obsolete
```

```bash
docker compose run --rm --no-deps backend python manage.py compilemessages -l en
```

---

## Deploy (produzione)

**https://languor.inoo.it**, sul homeserver accanto agli altri progetti. Push
sul branch `prod` → la GitHub Action (`.github/workflows/prod.yml`) fa ruff,
pytest, tsc ed eslint e pubblica `languorino-backend:prod` e
`languorino-web:prod` su ghcr.io → Watchtower (quello di cinemino) ricrea i
container. Le migrazioni girano all'avvio del backend. Watchtower aggiorna le
immagini ma non aggiunge servizi né reti: quando cambia
`deploy/compose.prod.yaml` va ricopiato a mano in `~/languorino` e poi
`docker compose -f compose.prod.yaml up -d`.

Primo avvio sul server:

1. DNS: record A per `languor.inoo.it` → l'IP del server (come gli altri progetti);
2. `~/languorino/compose.prod.yaml` (da `deploy/`) e `~/languorino/.env`
   (modello `deploy/.env.prod.example`, SMTP Brevo come gli altri);
3. il blocco `languor.inoo.it` del Caddyfile dell'edge (`deploy/edge/`,
   condiviso fra i progetti) copiato in `~/edge/` e ricaricato con
   `docker exec edge-caddy-1 caddy reload --config /etc/caddy/Caddyfile`, che
   non ferma gli altri;
4. `git push origin main:prod`, poi `cd ~/languorino && docker compose -f
   compose.prod.yaml up -d` e `createsuperuser`.

Backup notturni sul disco del server, a ogni avvio e poi ogni notte:
Postgres (servizio `backup`) in `~/languorino/backups/{daily,weekly,monthly,last}`
e i file caricati (servizio `media-backup`, volume `languorino_media`) in
`~/languorino/backups/media/`. Per la copia fuori dal server aggiungere la
cartella `backups` allo stack `~/offsite` (sorgenti in `soldino/deploy/offsite/`).

## Test

Backend con `pytest` + `factory-boy`: registrazione, login, conferma email,
reset e cambio password, mail nella lingua dell'utente, catalogo delle
traduzioni e scelta della lingua.
