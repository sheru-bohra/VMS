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
import json
from app.infrastructure.database import SessionLocal
from app.application.audit_integrity_service import verify_chain
db = SessionLocal()
try:
    result = verify_chain(db)
    print(json.dumps(result, indent=2))
finally:
    db.close()
`], { cwd: resolve(root, 'backend'), stdio: 'inherit', env });
process.exit(r.status ?? 1);
