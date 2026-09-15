import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { DEFAULT_USER_PREFERENCES } from '../utils/userPreferences';

const themeCss = readFileSync(
  resolve(dirname(fileURLToPath(import.meta.url)), '../styles/theme.css'),
  'utf8',
);

/**
 * Regression: dark content theme must not remap shared tokens on the whole admin-layout
 * (which inverted sidebar to light cream and workspace to dark).
 */
describe('theme regression — staff shell color contract', () => {
  it('default preference is Light (not System)', () => {
    expect(DEFAULT_USER_PREFERENCES.theme).toBe('light');
  });

  it('theme.css pins sidebar to dark navy independent of content theme', () => {
    expect(themeCss).toContain('.admin-layout .admin-sidebar');
    expect(themeCss).toContain('--vms-sidebar-bg: #0f172a');
    expect(themeCss).toContain('background: var(--vms-sidebar-bg)');
    expect(themeCss).not.toMatch(
      /\.admin-layout\[data-theme='dark']\s*\{[^}]*--color-navy-900/,
    );
    expect(themeCss).toContain('.admin-layout[data-theme=\'dark\'] .admin-main');
  });

  it('light workspace tokens restore original palette on admin-main', () => {
    expect(themeCss).toContain('[data-theme=\'light\'] .admin-main');
    expect(themeCss).toContain('--color-slate-100: #f1f5f9');
    expect(themeCss).toContain('.admin-main .admin-content');
    expect(themeCss).toContain('background: #f1f5f9');
  });

  it('dark theme does not set sidebar to light background', () => {
    const sidebarBlock = themeCss.match(/\.admin-layout \.admin-sidebar\s*\{[^}]+}/)?.[0] ?? '';
    expect(sidebarBlock).toContain('#0f172a');
    expect(sidebarBlock).not.toContain('#f1f5f9');
  });
});
