# Go-Live Cutover Runbook

Vendor-neutral deployment sequence. **Do not execute from VMS application UI.**

## Preconditions

- Release candidate report reviewed (`docs/release/release-candidate-report.md`)
- **Phase 16.2 production go-live decision: NO_GO** — staging environment not connected; live validations pending
- Go-live checklist complete (`docs/release/go-live-checklist.md`)
- Maintenance window approved
- On-call / escalation contacts defined by operations team

## Sequence

### 1. Approve release

Confirm release version and change record.

### 2. Backup / checkpoint

Infrastructure team: database backup + PITR checkpoint per `docs/runbooks/database-backup-recovery.md`.

### 3. Drain traffic (outer layer)

Load balancer / gateway stops routing new sessions to old instances.

### 4. Run database migration

```bash
npm run migrate
cd backend && python3 -m alembic current
```

Expected: revision at head (`014`).

### 5. Deploy application

Deploy new API and static frontend artifacts per platform procedure.

### 6. Readiness verification

- `GET /api/health/live`
- `GET /api/health/ready`
- Operations readiness page (database CONNECTED, schema CURRENT)

### 7. Staff SSO smoke

Global Admin Entra login → verify `/api/me`.

### 8. Public visitor smoke

Load registration URL for pilot location.

### 9. Graph smoke (if email required)

Send approved test message or verify notification queue processing.

### 10. Monitor

Follow `docs/release/post-deploy-smoke.md` and observation window guidance in production-readiness docs.

## Rollback triggers

See `docs/runbooks/rollback.md`. Examples:

- Auth unavailable for all staff
- Migration failure / schema mismatch
- Cross-location data exposure
- Registration or check-in unavailable
- Audit integrity BROKEN

## Rollback (high level)

1. Stop traffic to new version
2. Deploy previous application artifact if schema-compatible
3. If schema incompatible → escalate; forward-fix migration, not automatic downgrade
4. Verify health and audit integrity before resuming traffic

## Not performed by this phase

- DNS changes
- Cloud resource creation
- Automatic production deployment from VMS codebase
