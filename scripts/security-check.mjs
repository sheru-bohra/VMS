#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');

function runPageVerify() {
  const r = spawnSync('npm', ['run', 'page:verify'], { cwd: root, stdio: 'inherit' });
  return r.status === 0;
}

function checkEnv() {
  const r = spawnSync('python3', ['-c', `
from app.core.config import settings
try:
    settings.validate_environment()
    print("config_ok")
except Exception as e:
    print(f"config_fail: {e}")
    raise SystemExit(1)
`], { cwd: resolve(root, 'backend'), encoding: 'utf8' });
  if (r.status !== 0) {
    console.error(r.stdout || r.stderr);
    return false;
  }
  console.log('Environment validation passed (current APP_ENV).');
  return true;
}

const ok = runPageVerify() && checkEnv();
process.exit(ok ? 0 : 1);
