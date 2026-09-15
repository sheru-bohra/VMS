# Application Rollback Runbook

## Code rollback

1. Deploy previous application release artifact.
2. Confirm schema compatibility (database revision vs application-known migrations).
3. If schema is ahead of rolled-back code → do not run; escalate.

## Schema incompatible rollback

Prefer forward-fix migration rather than Alembic downgrade in production.

## Provider disablement

If an external integration blocks readiness, approved operators may disable optional providers via configuration and redeploy.

## Do not

- Run automatic `alembic downgrade` in production
- Expose migration controls in the admin UI
