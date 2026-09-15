#!/usr/bin/env node
/**
 * Pre-commit / CI repository secret scan.
 * Fails if known secret patterns appear in tracked source files.
 */
import { execSync } from 'node:child_process';
import { readFileSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');

const forbiddenPatterns = [
  { pattern: /9886769997/, skip: ['scripts/repo-secret-scan.mjs'] },
  { pattern: /GLOBAL_ADMIN_INITIAL_PASSWORD\s*=\s*[^\s#\s]/ },
  {
    pattern: /GLOBAL_ADMIN_INITIAL_PASSWORD\s*=\s*[^\s#]+/,
    skip: ['.env.example', '.env.docker.example', '.env.production.example', '.env.staging.example'],
  },
  { pattern: /ENTRA_CLIENT_SECRET\s*=\s*(?!CHANGE_ME)[^\s#]+/ },
  { pattern: /GRAPH_CLIENT_SECRET\s*=\s*(?!CHANGE_ME)[^\s#]+/ },
  {
    pattern: /postgresql\+psycopg:\/\/[^:]+:(?!CHANGE_ME|change-me|PASSWORD|\$\{)[^@\s]+@/,
    skip: ['docker-compose.yml'],
  },
  { pattern: /-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----/ },
  { pattern: /ghp_[A-Za-z0-9]{20,}/ },
  { pattern: /github_pat_[A-Za-z0-9_]+/ },
];

const scanExtensions = new Set([
  '.ts', '.tsx', '.js', '.mjs', '.cjs', '.py', '.json', '.yml', '.yaml',
  '.md', '.css', '.html', '.env', '.example', '.sh', '.sql',
]);

const alwaysSkip = new Set([
  'node_modules',
  'frontend/dist',
  'frontend/node_modules',
  '.git',
  'data',
  '.venv',
  'venv',
  '__pycache__',
  '.pytest_cache',
  'artifacts',
  'coverage',
  'htmlcov',
]);

function listFiles() {
  try {
    const out = execSync('git ls-files -z', { cwd: root, encoding: 'buffer' });
    return out.toString('utf8').split('\0').filter(Boolean);
  } catch {
    // Fresh repo without commits — walk known source roots
    const roots = ['backend', 'frontend/src', 'scripts', 'docs', '.github'];
    const files = [];
    for (const rel of roots) {
      const abs = resolve(root, rel);
      if (!existsSync(abs)) continue;
      const stack = [abs];
      while (stack.length) {
        const dir = stack.pop();
        for (const entry of execSync(`find "${dir}" -type f`, { encoding: 'utf8' }).trim().split('\n').filter(Boolean)) {
          const relPath = entry.replace(`${root}/`, '');
          if (!alwaysSkip.some((s) => relPath.includes(s))) files.push(relPath);
        }
      }
    }
    return [...new Set(files)];
  }
}

const hits = [];
for (const rel of listFiles()) {
  const ext = rel.slice(rel.lastIndexOf('.'));
  if (!scanExtensions.has(ext) && !rel.endsWith('.env.example') && !rel.includes('Dockerfile')) continue;
  if (rel === '.env' || rel.startsWith('.env.local')) continue;
  const content = readFileSync(resolve(root, rel), 'utf8');
  for (const rule of forbiddenPatterns) {
    if (rule.skip?.includes(rel)) continue;
    if (rule.pattern.test(content)) {
      hits.push({ file: rel, pattern: rule.pattern.toString() });
    }
  }
}

if (hits.length) {
  console.error('Repository secret scan FAILED:');
  for (const hit of hits) console.error(`  ${hit.file} matched ${hit.pattern}`);
  process.exit(1);
}

console.log('Repository secret scan PASS');
