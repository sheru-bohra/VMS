# Database Backup & Recovery

## Infrastructure expectations

Production PostgreSQL backups are **infrastructure-controlled**:

- Automated managed backups
- Point-in-time recovery (PITR)
- Encryption at rest
- Retention per business approval
- Periodic restore testing

Placeholders — set RPO/RTO with business and infrastructure teams.

## Logical backup (optional)

For release safety, operators may use `pg_dump` with credentials from secure secret management (never hardcode passwords).

## Recovery verification

After restore:

1. Verify Alembic revision at head
2. Run `npm run audit:verify`
3. Smoke-test critical workflows

## Phase 16.2 rehearsal status (2026-08-27)

**Not performed** — no approved staging PostgreSQL source/restore URLs were available in the validation workspace.

When staging infrastructure is ready, run:

```bash
export ENABLE_LIVE_INTEGRATION_TESTS=true
export ALLOW_POSTGRES_TEST_DATABASE=true
export TEST_POSTGRES_URL='postgresql://.../vms_uat_test'
export TEST_POSTGRES_RESTORE_URL='postgresql://.../vms_uat_restore'
npm run pg:restore-rehearsal
```

Record artifact: `artifacts/release/pg-backup-restore-rehearsal.json` (no passwords in output).

Infrastructure-level restore validation remains required before production go-live.

## Disaster recovery principle

- Application can be rebuilt from source and configuration
- PostgreSQL is the source of persistent business state
- Compliance uploads require persistent protected storage
- Encryption keys must be recoverable via approved secret management

## Key loss

Loss of `DOCUMENT_ENCRYPTION_KEY` may make encrypted compliance files unrecoverable. `AUDIT_INTEGRITY_KEY` must be backed up separately from the database it protects.
