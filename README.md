# Templatino

<!-- template:start -->
> **Questo è il template** dei progetti personali: le fondamenta comuni di
> [soldino](https://github.com/ImBiagio/soldino) e
> [regalino](https://github.com/ImBiagio/regalino) (e di
> [cinemino](https://github.com/ImBiagio/cinemino) per mail e deploy), senza
> il loro dominio. Dentro c'è anche il kit per lavorare con Claude: il modello
> di `CLAUDE.md`, le note standard del vault Obsidian e il modello degli ADR
> (in `.template/`, prima in claude-dev-kit).
>
> ### Progetto nuovo
>
> ```bash
> gh repo create ImBiagio/<nome> --private --template ImBiagio/templatino --clone
> cd <nome>
> scripts/init-project.sh <nome> --app 5177 --api 8030 --db 5437
> ```
>
> Lo script rinomina tutto (`templatino` → `<nome>`), imposta porte e dominio
> (`<nome senza "ino">.inoo.it`, cambiabile con `--domain`), crea `CLAUDE.md`
> e la cartella del progetto nel vault `Dev/`, toglie questa parte del README e
> poi cancella `.template/` e se stesso. Poi `docker compose up --build`.
>
> Porte già prese, da non riusare:
>
> | Progetto | App | API | Postgres |
> |---|---|---|---|
> | cinemino | 5173 | 8000 | — |
> | soldino | 5173 | 8000 | 5433 |
> | regalino | 5176 | 8020 | 5436 |
> | languorino | 5177 | 8030 | 5437 |
> | templatino | 5190 | 8090 | 5490 |
>
> ### Tenere il template aggiornato
>
> Un fix alle parti comuni (auth, mail, i18n, deploy, componenti UI) fatto in un
> progetto va portato anche qui, e viceversa: sono copie, non una libreria
> ([ADR 0001](docs/decisions/0001-stack.md)). Se cambia una regola di lavoro,
> va cambiata in `.template/CLAUDE.md.template` **e** nei `CLAUDE.md` dei
> progetti esistenti.
<!-- template:end -->

Descrizione del progetto, in due righe: per chi e quale problema risolve.

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
| App | http://localhost:5190 |
| API | http://localhost:8090/api |
| Docs OpenAPI | http://localhost:8090/api/docs/ |
| Admin Django | http://localhost:8090/admin/ |

Le porte sono diverse dagli altri progetti per farli girare insieme; per lo
stesso motivo il cookie di refresh si chiama `templatino_refresh`.

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
- **LLM**: chiave Gemini in `GEMINI_API_KEY` (vuota = funzioni spente), modello
  in `GEMINI_MODEL`.

---

## Struttura

```
backend/
├── config/settings/     base · dev · prod · test
├── templates/emails/    layout unico delle mail
└── apps/
    ├── core/            BaseModel, methods (token, hash, mail), i18n, task mail
    └── users/           User custom + auth JWT + mail dell'account
frontend/src/
├── api/hooks.ts         hook TanStack Query, una sezione per area
├── lib/                 client HTTP, auth, i18n, format, tipi
├── components/          UI M3, layout, dialog di conferma
└── features/            auth · account · home
deploy/                  compose di produzione, Caddy interno, edge condiviso
docs/decisions/          ADR (modello in 0000-modello.md)
```

### API

| | |
|---|---|
| `POST /api/auth/register` · `login` · `refresh` · `logout` | account e sessione (refresh nel cookie) |
| `POST /api/auth/verify-email/{token}` · `verify-email/resend` | conferma dell'indirizzo |
| `POST /api/auth/password` · `password-reset` · `password-reset/confirm` | cambio e reset della password |
| `GET/PATCH /api/me` | profilo (nome, lingua) |
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

**https://templat.inoo.it**, sul homeserver accanto agli altri progetti. Push
sul branch `prod` → la GitHub Action (`.github/workflows/prod.yml`) fa ruff,
pytest, tsc ed eslint e pubblica `templatino-backend:prod` e
`templatino-web:prod` su ghcr.io → Watchtower (quello di cinemino) ricrea i
container. Le migrazioni girano all'avvio del backend. Watchtower aggiorna le
immagini ma non aggiunge servizi né reti: quando cambia
`deploy/compose.prod.yaml` va ricopiato a mano in `~/templatino` e poi
`docker compose -f compose.prod.yaml up -d`.

Primo avvio sul server:

1. DNS: record A `templat` → l'IP del server (come `cinem`, `sold`, `regal`);
2. `~/templatino/compose.prod.yaml` (da `deploy/`) e `~/templatino/.env`
   (modello `deploy/.env.prod.example`, SMTP Brevo come gli altri);
3. il blocco `templat.inoo.it` del Caddyfile dell'edge (`deploy/edge/`,
   condiviso fra i progetti) copiato in `~/edge/` e ricaricato con
   `docker exec edge-caddy-1 caddy reload --config /etc/caddy/Caddyfile`, che
   non ferma gli altri;
4. `git push origin main:prod`, poi `cd ~/templatino && docker compose -f
   compose.prod.yaml up -d` e `createsuperuser`.

Backup notturni sul disco del server, a ogni avvio e poi ogni notte:
Postgres (servizio `backup`) in `~/templatino/backups/{daily,weekly,monthly,last}`
e i file caricati (servizio `media-backup`, volume `templatino_media`) in
`~/templatino/backups/media/`. Per la copia fuori dal server aggiungere la
cartella `backups` allo stack `~/offsite` (sorgenti in `soldino/deploy/offsite/`).

## Test

Backend con `pytest` + `factory-boy`: registrazione, login, conferma email,
reset e cambio password, mail nella lingua dell'utente, catalogo delle
traduzioni e scelta della lingua.
