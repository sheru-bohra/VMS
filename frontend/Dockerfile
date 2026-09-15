# syntax=docker/dockerfile:1

FROM node:20-bookworm-slim AS build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./frontend/
RUN cd frontend && npm ci

COPY frontend ./frontend
COPY .env.docker.example ./.env

ARG VITE_AUTH_MODE=vms_native
ARG VITE_ENABLE_SOURCEMAPS=false

ENV VITE_AUTH_MODE=${VITE_AUTH_MODE} \
    VITE_ENABLE_SOURCEMAPS=${VITE_ENABLE_SOURCEMAPS}

RUN cd frontend && npm run build

FROM nginx:1.27-alpine AS runtime

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/ >/dev/null || exit 1
