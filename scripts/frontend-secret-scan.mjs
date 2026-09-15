#!/usr/bin/env node
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const dist = join(root, 'frontend', 'dist');

const forbidden = [
  'GRAPH_CLIENT_SECRET',
  'DOCUMENT_ENCRYPTION_KEY',
  'VMS_DATA_ENCRYPTION_KEY',
  'AUDIT_INTEGRITY_KEY',
  'postgresql://user:password',
  'sqlite:///:memory:?password=',
];

function walk(dir, files = []) {
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    const stat = statSync(path);
    if (stat.isDirectory()) walk(path, files);
    else if (/\.(js|css|html|map)$/i.test(entry)) files.push(path);
  }
  return files;
}

if (!existsSync(dist)) {
  console.error('Frontend dist/ not found. Run npm run build first.');
  process.exit(1);
}

const hits = [];
for (const file of walk(dist)) {
  const content = readFileSync(file, 'utf8');
  for (const token of forbidden) {
    if (content.includes(token)) hits.push({ file, token });
  }
}

if (hits.length) {
  console.error('Frontend secret scan FAILED:');
  for (const hit of hits) console.error(`  ${hit.token} in ${hit.file}`);
  process.exit(1);
}

console.log('Frontend secret scan PASS');
