# Database Migrations Runbook

## Before migration

1. Obtain change approval and maintenance window if required.
2. Take infrastructure backup / PITR checkpoint (see database-backup-recovery.md).
3. Verify target environment `DATABASE_URL` points to the correct cluster.

## Migrate

```bash
npm run migrate
```

Verify:

```bash
cd backend && python3 -m alembic current
```

Expected: revision `014` (head).

## After migration

1. Run smoke checks (`/api/health/live`, `/api/health/ready`).
2. Roll out or restart application instances.
3. Monitor logs and operations readiness page.

## Rollback

Do **not** run Alembic downgrade in production by default. Prefer application rollback when schema-compatible, or ship a forward-fix migration.
