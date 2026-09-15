# Audit Integrity Runbook

## Audit Integrity = BROKEN

1. Do **not** auto-repair the chain from the application.
2. Preserve evidence and restrict administrative changes as appropriate.
3. Investigate database history and recent deployments.
4. Verify `AUDIT_INTEGRITY_KEY` matches the key used when events were sealed.
5. Escalate to security and infrastructure teams.

Never delete audit evidence.

## Verification

```bash
npm run audit:verify
```

Readiness surfaces the most recent cached integrity state; full verification is not run on every readiness request.
