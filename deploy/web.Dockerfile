# Build statica del frontend...
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ .
# Senza VITE_API_BASE_URL il client chiama l'API sullo stesso dominio.
RUN npm run build

# ...servita da Caddy, che fa anche da reverse proxy verso Django.
FROM caddy:2-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv/www
