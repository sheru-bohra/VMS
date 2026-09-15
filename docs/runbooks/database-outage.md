# Database Outage Runbook

## Symptoms

- `/api/health/live` → OK (process alive)
- `/api/health/ready` → 503 `DATABASE_UNAVAILABLE` or schema errors
- Business APIs → 503 `DATABASE_UNAVAILABLE`

## Response

1. Stop routing traffic to affected instances (load balancer / gateway).
2. Preserve application logs (no stack traces exposed to clients in production).
3. Restore database availability via infrastructure procedures.
4. Verify schema at Alembic head before resuming traffic.
5. Run `npm run audit:verify`.
6. Resume traffic gradually and monitor operations readiness.

Do not auto-retry arbitrary failed writes from the application layer.
