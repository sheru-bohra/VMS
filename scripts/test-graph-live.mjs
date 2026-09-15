#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
if (process.env.ENABLE_LIVE_INTEGRATION_TESTS !== 'true') {
  console.log('NOT_CONFIGURED: ENABLE_LIVE_INTEGRATION_TESTS=true required');
  process.exit(1);
}
if (!process.env.EMAIL_LIVE_TEST_RECIPIENT) {
  console.log('NOT_CONFIGURED: EMAIL_LIVE_TEST_RECIPIENT required');
  process.exit(1);
}
const result = spawnSync(
  'python3',
  ['-m', 'pytest', 'tests/integration/live/test_graph_live.py', '-v'],
  {
    cwd: resolve(root, 'backend'),
    env: process.env,
    encoding: 'utf8',
  },
);
process.stdout.write(result.stdout || '');
process.stderr.write(result.stderr || '');
if (result.status === 0) {
  console.log('GRAPH LIVE: PASS');
} else {
  console.log('GRAPH LIVE: FAIL');
}
process.exit(result.status ?? 1);
