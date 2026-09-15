#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const backend = resolve(root, 'backend');

const releaseFiles = [
  'tests/test_phase16_release.py',
  'tests/test_phase13.py',
  'tests/test_phase14_1.py',
  'tests/test_phase10.py',
  'tests/test_phase9.py',
];

const releaseFilter =
  'idor or mass_assignment or cors or formula or health_live or duplicate_active_emergency or forbidden or site_admin';

function runPytest(args) {
  return spawnSync('python3', ['-m', 'pytest', ...args, '-v'], {
    cwd: backend,
    encoding: 'utf8',
  });
}

const subset = runPytest([...releaseFiles, '-k', releaseFilter]);
process.stdout.write(subset.stdout || '');
process.stderr.write(subset.stderr || '');

const closure = runPytest(['tests/test_phase16_1_closure.py']);
process.stdout.write(closure.stdout || '');
process.stderr.write(closure.stderr || '');

const ok = (subset.status ?? 1) === 0 && (closure.status ?? 1) === 0;
process.exit(ok ? 0 : 1);
