# Build statica del frontend...
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ .
# DSN pubblica del progetto GlitchTip del frontend (variabile del repo
# SENTRY_DSN_FRONTEND su GitHub): vuota, il frontend non manda errori.
ARG VITE_SENTRY_DSN=""
ENV VITE_SENTRY_DSN=$VITE_SENTRY_DSN
# Senza VITE_API_BASE_URL il client chiama l'API sullo stesso dominio.
RUN npm run build

# ...servita da Caddy, che fa anche da reverse proxy verso Django.
FROM caddy:2-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv/www
