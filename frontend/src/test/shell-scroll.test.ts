import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const stylesDir = resolve(dirname(fileURLToPath(import.meta.url)), '../styles');

const adminCss = readFileSync(resolve(stylesDir, 'admin.css'), 'utf8');
const adminPagesCss = readFileSync(resolve(stylesDir, 'admin-pages.css'), 'utf8');
const profileMenuCss = readFileSync(resolve(stylesDir, 'profile-menu.css'), 'utf8');

describe('shell scroll isolation', () => {
  it('admin layout uses viewport height without outer page scroll', () => {
    expect(adminCss).toMatch(/\.admin-layout\s*\{[^}]*overflow:\s*hidden/);
    expect(adminCss).toMatch(/\.admin-layout\s*\{[^}]*height:\s*100dvh/);
  });

  it('sidebar and main content have independent scroll regions', () => {
    expect(adminCss).toMatch(/\.admin-sidebar__nav\s*\{[^}]*overflow-y:\s*auto/);
    expect(adminCss).toMatch(/\.admin-content\s*\{[^}]*overflow-y:\s*auto/);
    expect(adminCss).toMatch(/overscroll-behavior-y:\s*contain/);
  });
});

describe('card boundary styles', () => {
  it('defines shared admin-card with visible border', () => {
    expect(adminPagesCss).toContain('.admin-card');
    expect(adminPagesCss).toMatch(/\.admin-card\s*\{[^}]*border:\s*1px solid var\(--color-slate-200\)/);
    expect(adminPagesCss).toMatch(/\.admin-card\s*\{[^}]*background:\s*var\(--color-white\)/);
  });

  it('defines metric-card for KPI blocks', () => {
    expect(adminPagesCss).toContain('.metric-card');
    expect(adminPagesCss).toContain('.metric-card__label');
    expect(adminPagesCss).toContain('.metric-card__value');
    expect(adminPagesCss).toContain('.kpi-grid');
  });
});

describe('profile menu scroll containment', () => {
  it('dropdown has independent scroll and overscroll containment', () => {
    expect(profileMenuCss).toMatch(/\.profile-menu__dropdown\s*\{[^}]*overflow-y:\s*auto/);
    expect(profileMenuCss).toMatch(/\.profile-menu__dropdown\s*\{[^}]*overscroll-behavior:\s*contain/);
    expect(profileMenuCss).toMatch(/max-height:\s*min\(/);
  });
});
