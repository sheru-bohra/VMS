#!/usr/bin/env node
/**
 * Verify locked pages have not been modified.
 * Usage: npm run page:verify
 */
import { createHash } from 'node:crypto';
import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { join, relative, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..');
const LOCKS_FILE = join(ROOT, '.vms', 'page-locks.json');

function hashFile(filePath) {
  const content = readFileSync(filePath);
  return createHash('sha256').update(content).digest('hex');
}

function collectFiles(basePath) {
  const fullPath = join(ROOT, basePath);
  if (!existsSync(fullPath)) return [];
  const files = [];
  function walk(dir) {
    for (const entry of readdirSync(dir)) {
      const p = join(dir, entry);
      const stat = statSync(p);
      if (stat.isDirectory()) walk(p);
      else if (/\.(tsx?|jsx?|css|scss)$/.test(entry)) files.push(p);
    }
  }
  if (statSync(fullPath).isDirectory()) walk(fullPath);
  else files.push(fullPath);
  return files;
}

if (!existsSync(LOCKS_FILE)) {
  console.log('No page locks registered. Verification passed.');
  process.exit(0);
}

const locks = JSON.parse(readFileSync(LOCKS_FILE, 'utf-8'));
let violations = 0;

for (const page of locks.pages) {
  if (page.status !== 'LOCKED') continue;

  const currentHashes = {};
  for (const basePath of page.paths) {
    const files = collectFiles(basePath);
    for (const file of files) {
      const rel = relative(ROOT, file);
      currentHashes[rel] = hashFile(file);
    }
  }

  for (const [file, expectedHash] of Object.entries(page.fileHashes || {})) {
    const fullPath = join(ROOT, file);
    if (!existsSync(fullPath)) {
      console.error('LOCK VIOLATION');
      console.error(`Page: ${page.id}`);
      console.error(`Missing file: ${file}`);
      console.error('Explicit approval required before changing locked implementation.');
      violations++;
      continue;
    }
    const currentHash = hashFile(fullPath);
    if (currentHash !== expectedHash) {
      console.error('LOCK VIOLATION');
      console.error(`Page: ${page.id}`);
      console.error(`Modified file: ${file}`);
      console.error('Explicit approval required before changing locked implementation.');
      violations++;
    }
  }

  for (const file of Object.keys(currentHashes)) {
    if (!page.fileHashes?.[file]) {
      console.error('LOCK VIOLATION');
      console.error(`Page: ${page.id}`);
      console.error(`New file added: ${file}`);
      console.error('Explicit approval required before changing locked implementation.');
      violations++;
    }
  }
}

if (violations > 0) {
  console.error(`\n${violations} lock violation(s) detected.`);
  process.exit(1);
}

console.log(`All ${locks.pages.length} locked page(s) verified. No violations.`);
