import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');

describe('Access Operations UI enrichment', () => {
  const page = readFileSync(resolve(root, 'pages/access-operations/AccessOperationsPage.tsx'), 'utf8');
  const css = readFileSync(resolve(root, 'styles/access-operations-page.css'), 'utf8');

  it('uses AdminTabs with all four operational tabs', () => {
    expect(page).toContain('AdminTabs');
    expect(page).toContain('Active Access');
    expect(page).toContain('Needs Attention');
    expect(page).toContain('Badge Print Jobs');
    expect(page).toContain('Provider Status');
    expect(page).not.toContain('admin-chip-row');
  });

  it('uses dedicated filter toolbar and section cards', () => {
    expect(page).toContain('access-ops-filters');
    expect(page).toContain('access-ops-filter--location');
    expect(page).toContain('access-ops-filter--state');
    expect(page).toContain('access-ops-filter--search');
    expect(page).toContain('section-card access-ops-results');
  });

  it('uses EmptyState for zero-record views', () => {
    expect(page).toContain('No active access credentials');
    expect(page).toContain('No access issues need attention');
    expect(page).toContain('No badge print jobs');
  });

  it('uses semantic status badges without changing state logic', () => {
    expect(page).toContain('StatusBadge');
    expect(page).toContain('CHECKED_OUT_ACCESS_ACTIVE');
    expect(page).toContain('Retry Revocation');
  });

  it('styles support theme-aware tabs, filters, and compact density', () => {
    expect(css).toContain('.access-ops-tabs');
    expect(css).toContain('.access-ops-filters');
    expect(css).toContain("[data-theme='dark']");
    expect(css).toContain("data-density='compact'");
  });
});
