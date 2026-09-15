#!/usr/bin/env node
/**
 * Validate production-oriented configuration without deploying or mutating runtime.
 */
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const envFile = process.env.PRODUCTION_CHECK_ENV || resolve(root, '.env.production.check');

function loadEnvFile(path) {
  if (!existsSync(path)) return {};
  const out = {};
  for (const line of readFileSync(path, 'utf8').split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const idx = trimmed.indexOf('=');
    if (idx === -1) continue;
    out[trimmed.slice(0, idx).trim()] = trimmed.slice(idx + 1).trim();
  }
  return out;
}

const fileEnv = loadEnvFile(envFile);
const merged = { ...process.env, ...fileEnv };

const result = spawnSync('python3', ['scripts/production_check.py'], {
  cwd: resolve(root, 'backend'),
  env: merged,
  encoding: 'utf8',
});

process.stdout.write(result.stdout || '');
process.stderr.write(result.stderr || '');
process.exit(result.status ?? 1);
