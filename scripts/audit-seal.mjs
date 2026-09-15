#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');

const env = { ...process.env };
if (!env.AUDIT_INTEGRITY_KEY) {
  env.AUDIT_INTEGRITY_KEY = 'phase13-audit-integrity-key-for-local-vms-session-only-32c';
}

const r = spawnSync('python3', ['-c', `
from app.infrastructure.database import SessionLocal
from app.application.audit_integrity_service import backfill_unsealed_events
db = SessionLocal()
try:
    n = backfill_unsealed_events(db)
    db.commit()
    print(f"Sealed {n} legacy audit events.")
finally:
    db.close()
`], { cwd: resolve(root, 'backend'), stdio: 'inherit', env });
process.exit(r.status ?? 1);
