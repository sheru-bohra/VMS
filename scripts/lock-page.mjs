#!/usr/bin/env node
/**
 * Lock a page by computing SHA-256 hashes of its source files.
 * Usage: npm run page:lock -- dashboard
 */
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { join, relative, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..');
const LOCKS_FILE = join(ROOT, '.vms', 'page-locks.json');

const PAGE_PATH_MAP = {
  dashboard: { route: '/dashboard', paths: ['frontend/src/pages/dashboard'] },
  'admin-shell': { route: '/admin', paths: ['frontend/src/layouts/AdminLayout', 'frontend/src/components/admin'] },
  'visitor-shell': { route: '/visit', paths: ['frontend/src/pages/visit/VisitorWelcomePage.tsx', 'frontend/src/layouts/VisitorLayout.tsx'] },
  'visitor-registration': { route: '/visit/register', paths: ['frontend/src/pages/visit/VisitorRegistrationPage.tsx', 'frontend/src/pages/visit/RegistrationSuccessPage.tsx', 'frontend/src/components/visit'] },
  'self-registrations': { route: '/self-registrations', paths: ['frontend/src/pages/self-registrations'] },
  'approvals': { route: '/approvals', paths: ['frontend/src/pages/approvals'] },
  'expected-today': { route: '/expected-today', paths: ['frontend/src/pages/expected-today'] },
  'onsite-now': { route: '/onsite-now', paths: ['frontend/src/pages/onsite'] },
  'invitations': { route: '/invitations', paths: ['frontend/src/pages/invitations'] },
  'visitor-invitation': { route: '/visit/invitation', paths: ['frontend/src/pages/visit/VisitorInvitationPage.tsx'] },
  'badge-print': { route: '/badges', paths: ['frontend/src/pages/badges', 'frontend/src/styles/badge-print.css'] },
  'host-approval': { route: '/host/approval', paths: ['frontend/src/pages/host/HostApprovalPage.tsx'] },
  'watchlist': { route: '/watchlist', paths: ['frontend/src/pages/watchlist'] },
  'security-review': { route: '/security-review', paths: ['frontend/src/pages/security-review'] },
  'vendors-contractors': { route: '/vendors-contractors', paths: ['frontend/src/pages/vendors'] },
  'vendor-visit-create': { route: '/vendors-contractors/new-visit', paths: ['frontend/src/pages/vendors/CreateVendorVisitPage.tsx'] },
  'management-dashboard': { route: '/dashboard', paths: ['frontend/src/pages/dashboard'] },
  reports: { route: '/reports', paths: ['frontend/src/pages/reports'] },
  'vms-copilot': { route: '/vms-copilot', paths: ['frontend/src/pages/vms-copilot'] },
  login: { route: '/login', paths: ['frontend/src/pages/login', 'frontend/src/pages/auth', 'frontend/src/styles/login.css'] },
  'administration-users': { route: '/administration/users', paths: ['frontend/src/pages/administration/AdministrationUsersPage.tsx'] },
  'privacy-security': { route: '/administration/privacy-security', paths: ['frontend/src/pages/administration/PrivacySecurityPage.tsx'] },
  'access-operations': { route: '/access-operations', paths: ['frontend/src/pages/access-operations'] },
  'access-badges-admin': { route: '/administration/access-badges', paths: ['frontend/src/pages/administration/AccessBadgesAdminPage.tsx'] },
  locations: { route: '/locations', paths: ['frontend/src/pages/locations', 'frontend/src/styles/locations-page.css'] },
};

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

const pageId = process.argv[2];
if (!pageId) {
  console.error('Usage: npm run page:lock -- <page-id>');
  console.error('Known pages:', Object.keys(PAGE_PATH_MAP).join(', '));
  process.exit(1);
}

const config = PAGE_PATH_MAP[pageId];
if (!config) {
  console.error(`Unknown page: ${pageId}`);
  console.error('Known pages:', Object.keys(PAGE_PATH_MAP).join(', '));
  process.exit(1);
}

const locks = JSON.parse(readFileSync(LOCKS_FILE, 'utf-8'));
const fileHashes = {};
let totalFiles = 0;

for (const basePath of config.paths) {
  const files = collectFiles(basePath);
  for (const file of files) {
    const rel = relative(ROOT, file);
    fileHashes[rel] = hashFile(file);
    totalFiles++;
  }
}

if (totalFiles === 0) {
  console.error(`No files found for page "${pageId}" in paths: ${config.paths.join(', ')}`);
  process.exit(1);
}

const entry = {
  id: pageId,
  route: config.route,
  status: 'LOCKED',
  paths: config.paths,
  lockedAt: new Date().toISOString(),
  fileHashes,
};

const idx = locks.pages.findIndex((p) => p.id === pageId);
if (idx >= 0) locks.pages[idx] = entry;
else locks.pages.push(entry);

writeFileSync(LOCKS_FILE, JSON.stringify(locks, null, 2) + '\n');
console.log(`Page "${pageId}" locked successfully.`);
console.log(`  Route: ${config.route}`);
console.log(`  Files: ${totalFiles}`);
console.log(`  Locked at: ${entry.lockedAt}`);
