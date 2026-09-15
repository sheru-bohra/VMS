# Visitor Management System (VMS)

Production foundation for a dedicated Visitor Management System.

**Local URL:** http://localhost:7272

## Requirements

- Node.js 20+
- Python 3.11+
- npm

## Initial Setup

```bash
# Copy environment configuration
cp .env.example .env

# Install all dependencies
npm install
cd frontend && npm install && cd ..
cd backend && pip install -r requirements.txt && cd ..

# Run database migrations
npm run migrate
```

Or use the combined install:

```bash
npm run install:all
```

## Run Development

```bash
npm run dev
```

This starts both backend (port 7273) and frontend (port 7272). Access the application at:

**http://localhost:7272**

API requests from the frontend use `/api/...` and are proxied to the backend.

## Architecture

### Backend (`backend/`)

Modular monolith with FastAPI:

- `app/domain/` — entities, enums, visit state rules
- `app/application/` — services (auth, audit, bootstrap)
- `app/infrastructure/` — database, SQLAlchemy
- `app/presentation/` — API routes, dependencies, schemas
- `app/core/` — configuration, error handling

Database: SQLite for local dev (`data/vms-local.db`). Configurable via `DATABASE_URL`.

### Frontend (`frontend/`)

React + TypeScript + Vite:

- `src/app/` — application root and routing
- `src/layouts/` — admin and visitor layouts
- `src/pages/` — page components
- `src/components/` — reusable UI
- `src/services/` — API client
- `src/utils/` — permission helpers
- `src/hooks/` — React hooks
- `src/styles/` — global and module CSS

## Database Migrations

```bash
npm run migrate
```

Alembic migrations live in `backend/alembic/versions/`.

## Testing

```bash
npm test
```

Or individually:

```bash
npm run test:backend
npm run test:frontend
```

## Page Locking / Freezing

When a page is completed and approved, lock it:

```bash
npm run page:lock -- dashboard
```

Verify locked pages have not been modified:

```bash
npm run page:verify
```

Lock registry: `.vms/page-locks.json`

## Development Authentication

With `APP_ENV=development`, `AUTH_MODE=dev`, `DEV_AUTH_ENABLED=true`, and `EMAIL_PROVIDER=dev_outbox`, local development works without Microsoft credentials. The backend auto-authenticates as the bootstrap owner unless `X-Dev-User-Email` is sent from the frontend. This cannot run when `APP_ENV=production`.

For local VMS Native authentication, use `AUTH_MODE=vms_native` and set `GLOBAL_ADMIN_INITIAL_PASSWORD` only in your local `.env` (never commit it).

## Production Authentication

Production requires:

- `APP_ENV=production`
- `AUTH_MODE=vms_native`
- `DEV_AUTH_ENABLED=false`
- PostgreSQL `DATABASE_URL`
- Strong `AUDIT_INTEGRITY_KEY`, `DOCUMENT_ENCRYPTION_KEY`, and `VMS_DATA_ENCRYPTION_KEY`

See `.env.production.example` for the full production variable list. Microsoft Entra ID remains optional as a secondary provider; Microsoft Graph is not used.

## Docker

Container images are published to GitHub Container Registry (GHCR):

- `ghcr.io/sheru-bohra/vms-backend`
- `ghcr.io/sheru-bohra/vms-frontend`

### Build images locally

```bash
docker build -f backend/Dockerfile -t ghcr.io/sheru-bohra/vms-backend:local .
docker build -f frontend/Dockerfile -t ghcr.io/sheru-bohra/vms-frontend:local .
```

### Run with Docker Compose (PostgreSQL)

```bash
cp .env.docker.example .env.docker.local
# Edit .env.docker.local — set POSTGRES_PASSWORD and security keys (32+ chars). Never commit this file.

docker compose --env-file .env.docker.local build
docker compose --env-file .env.docker.local --profile tools run --rm migrate
docker compose --env-file .env.docker.local up -d
```

- Frontend: http://localhost:7272
- Backend API: http://localhost:7273/api/health
- Uploads are stored in the `vms_uploads` Docker volume (not in the image)
- Production containers do **not** auto-run Alembic migrations on startup

### Health endpoints

- `GET /api/health` — process health
- `GET /api/health/live` — liveness
- `GET /api/health/ready` — readiness (database, schema, audit, provider checks)

## Security checks

```bash
npm run repo:secret-scan
npm run frontend:secret-scan   # requires npm run build first
npm run page:verify
```

## Optional Microsoft Entra ID

Entra OIDC can be enabled as an optional provider. See `.env.example` for Entra placeholders. Pre-provision users at `/administration/users` before Entra sign-in.

## Roles

- `GLOBAL_ADMIN` — full VMS access
- `HEAD_ADMIN` — multi-site management and analytics
- `SITE_ADMIN` — operational site access (no management analytics/reports)
