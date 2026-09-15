# Production Readiness

Phase 15 prepares VMS for enterprise deployment without performing deployment.

## Topology (vendor-neutral)

```
HTTPS ingress / corporate gateway
        ↓
Frontend static application
        ↓
VMS API instances (stateless, multiple processes)
        ↓
PostgreSQL
```

External providers: Entra ID, Microsoft Graph email, ClamAV, access control, badge printer.

## Development vs Production

| Environment | Database | Auth | Notes |
|-------------|----------|------|-------|
| Development | SQLite | dev / Entra | `npm run dev` — no PostgreSQL required |
| Production | PostgreSQL | Entra only | SQLite rejected when `APP_ENV=production` |

## Database migrations

- Run **before** application rollout: `npm run migrate`
- Application startup verifies schema at Alembic head in production; it does **not** auto-migrate.
- Rollback prefers application rollback when schema-compatible, or forward-fix migrations — not Alembic downgrade in production.

## Scheduler coordination

Multiple API instances use database-backed `runtime_leases` so only one process runs each scheduler cycle per lease name.

## PostgreSQL validation states

- **COMPATIBILITY_TESTED** — code and migrations support PostgreSQL
- **LIVE_VALIDATED** — only after real `TEST_POSTGRES_URL` integration tests
- Run optional live suite: `npm run test:postgres` (requires `ALLOW_POSTGRES_TEST_DATABASE=true`)

## Commands

- `npm run test:release` — workflow-focused regression subset
- `npm run rc:check` — full release candidate orchestration (tests, audit, build, perf smoke)
- `npm run perf:smoke` — performance baseline (writes `artifacts/release/perf-smoke.json`)
- `npm run test:postgres` / `test:clamav-live` / `test:graph-live` — explicit live integration (require `ENABLE_LIVE_INTEGRATION_TESTS=true`)

Release matrix output: `artifacts/release/release-readiness.json` (generated, gitignored).

## Phase 16 release candidate

Release version via `APP_RELEASE_VERSION` (e.g. `1.0.0-rc1`). Integration states follow evidence-based classification: NOT_CONFIGURED → IMPLEMENTED → MOCK_TESTED → LIVE_VALIDATED → UAT_APPROVED → PRODUCTION_READY.

Manual UAT checklist: `docs/uat/final-uat-checklist.md`


## PostgreSQL server timezone

Recommend PostgreSQL server and session timezone **UTC**. Application displays using Location timezone.

## Secret management

Secrets are injected via secure runtime environment. Compatible future targets: Azure Key Vault, AWS Secrets Manager, HashiCorp Vault (not integrated in Phase 15).

## Key loss warning

Loss of `DOCUMENT_ENCRYPTION_KEY` may make encrypted compliance files unrecoverable. `AUDIT_INTEGRITY_KEY` must not be stored in the same database it protects.
