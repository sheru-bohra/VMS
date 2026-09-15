# Go-Live Checklist

Use before production cutover. Vendor-neutral; infrastructure team executes deployment steps.

**Phase 16.1 automated closure (2026-08-27):** regression, audit, security, build, secret scan, and perf smoke **PASS**. Items below remain open for production.

## Code & build

- [x] Release version set (`APP_RELEASE_VERSION=1.0.0-rc1`)
- [ ] `npm run rc:check` full PASS (fails `production_check` in dev SQLite — re-run in staging)
- [x] Frontend production build artifact builds (`npm run build`)
- [x] No secrets in build output (`npm run frontend:secret-scan`)

## Database

- [ ] Backup / PITR checkpoint taken (infrastructure)
- [x] `alembic upgrade head` verified locally (SQLite dev)
- [ ] `alembic current` equals head (`014`) on production PostgreSQL
- [ ] Schema verified via `/api/health/ready` in staging/production
- [ ] Live PostgreSQL suite (`npm run test:postgres`) on approved test DB
- [ ] Backup/restore rehearsal (`npm run pg:restore-rehearsal`)

## Authentication

- [ ] `AUTH_MODE=entra` in production
- [ ] Entra live validation completed (browser UAT — all personas)
- [ ] VMS users pre-provisioned (no JIT)

## Email

- [ ] Graph credentials configured
- [ ] Live test email delivered to approved mailbox
- [ ] `EMAIL_PROVIDER=ms_graph`

## Security

- [x] `npm run security:check` PASS (dev run)
- [x] `npm run audit:verify` VALID
- [ ] Encryption keys in secret management (not on app host only)
- [ ] CORS origins explicit (no wildcard)
- [ ] `RATE_LIMIT_BACKEND=database`

## File scanning

- [ ] `FILE_SCANNER_PROVIDER=clamav` if compliance uploads enabled
- [ ] ClamAV live validated (clean + EICAR)

## Optional integrations

- [x] `ACCESS_CONTROL_ENABLED=false` unless live-validated
- [x] `BADGE_PRINTER_ENABLED=false` unless live-validated
- [x] `AI_ENABLED=false` for initial production

## Operations

- [ ] Operations readiness page accessible to Global Admin (staging)
- [ ] Scheduler leases healthy after multi-instance deploy
- [ ] Monitoring: health/live, health/ready, notification backlog

## UAT sign-off

- [ ] `docs/uat/final-uat-checklist.md` completed by operators

## Approvals

- [ ] Product owner sign-off
- [ ] Security sign-off
- [ ] Operations sign-off

**Phase 16.3:** Staging validation **blocked** — environment is `development` / SQLite / `dev` auth. No live validation performed.

**Production go-live decision:** NO_GO

