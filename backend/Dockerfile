FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .

COPY . .

# --- dev: dipendenze di sviluppo e test ---
FROM base AS dev
# gettext: makemessages / compilemessages (i .mo sono nel repo, in prod non serve).
RUN apt-get update && apt-get install -y --no-install-recommends gettext \
    && rm -rf /var/lib/apt/lists/*
RUN pip install -e ".[dev]"

# --- prod ---
FROM base AS prod
ENV DJANGO_SETTINGS_MODULE=config.settings.prod
# Gli statici dell'admin finiscono nell'immagine (li serve whitenoise). La
# SECRET_KEY fittizia serve solo a far partire i settings durante la build:
# quella vera arriva dal .env all'avvio.
RUN DJANGO_SECRET_KEY=collectstatic-build python manage.py collectstatic --noinput
# Utente non root: un'eventuale RCE resta confinata nel container.
# chmod: il codice dev'essere leggibile dall'utente non root qualunque siano i
# permessi del checkout da cui parte la build.
# --create-home: gunicorn 23+ apre il suo control socket nella home.
# /app/media e' il volume delle foto: creata qui di appuser, cosi' il volume
# nuovo nasce gia' scrivibile da lui.
RUN useradd --system --create-home --uid 10001 appuser \
    && mkdir -p /app/media \
    && chmod -R a+rX /app \
    && chown -R appuser /app/staticfiles /app/media
USER appuser
EXPOSE 8000
# Migrazioni a ogni avvio (idempotenti). worker e beat usano la stessa immagine
# con un altro command nel compose di produzione.
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-3} --timeout 120"]
