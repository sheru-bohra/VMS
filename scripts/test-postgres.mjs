#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const url = process.env.TEST_POSTGRES_URL;
const allowed = process.env.ALLOW_POSTGRES_TEST_DATABASE === 'true';
const liveEnabled = process.env.ENABLE_LIVE_INTEGRATION_TESTS === 'true';

if (!url) {
  console.log('TEST_POSTGRES_URL is not set. PostgreSQL integration suite skipped.');
  console.log(
    'Set TEST_POSTGRES_URL, ALLOW_POSTGRES_TEST_DATABASE=true, and ENABLE_LIVE_INTEGRATION_TESTS=true to run live PostgreSQL tests.',
  );
  process.exit(0);
}

if (!allowed) {
  console.log('ALLOW_POSTGRES_TEST_DATABASE=true is required to run PostgreSQL integration tests.');
  process.exit(1);
}

if (!liveEnabled) {
  console.log('ENABLE_LIVE_INTEGRATION_TESTS=true is required to run PostgreSQL integration tests.');
  process.exit(1);
}

const result = spawnSync(
  'python3',
  ['-m', 'pytest', 'tests/integration/postgres/', '-v'],
  {
    cwd: resolve(root, 'backend'),
    env: {
      ...process.env,
      TEST_POSTGRES_URL: url,
      ALLOW_POSTGRES_TEST_DATABASE: 'true',
      ENABLE_LIVE_INTEGRATION_TESTS: 'true',
    },
    encoding: 'utf8',
  },
);

process.stdout.write(result.stdout || '');
process.stderr.write(result.stderr || '');
process.exit(result.status ?? 1);
