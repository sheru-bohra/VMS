import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');

const themeCss = readFileSync(resolve(root, 'styles/theme.css'), 'utf8');
const staffUiCss = readFileSync(resolve(root, 'styles/vms-staff-ui.css'), 'utf8');
const adminLayout = readFileSync(resolve(root, 'layouts/AdminLayout.tsx'), 'utf8');
const dashboardPage = readFileSync(resolve(root, 'pages/dashboard/DashboardPage.tsx'), 'utf8');

describe('enterprise UI — design system semantics', () => {
  it('AdminLayout imports staff shell design system CSS', () => {
    expect(adminLayout).toContain('vms-staff-ui.css');
    expect(adminLayout).toContain('vms-reference-shell.css');
    expect(adminLayout).toContain('vms-enrichment.css');
  });

  it('theme.css defines light and dark vms semantic tokens on admin-main', () => {
    expect(themeCss).toContain('--vms-page-bg');
    expect(themeCss).toContain('--vms-surface');
    expect(themeCss).toContain('--vms-text-primary');
    expect(themeCss).toContain('[data-theme=\'light\'] .admin-main');
    expect(themeCss).toContain('[data-theme=\'dark\'] .admin-main');
  });

  it('light theme uses dark primary text on light surfaces', () => {
    const lightBlock = themeCss.match(
      /\.admin-layout\[data-theme='light'\] \.admin-main[\s\S]*?--vms-text-primary: #0f172a/,
    );
    expect(lightBlock).not.toBeNull();
    expect(themeCss).toMatch(
      /\.admin-layout\[data-theme='light'\] \.admin-main[\s\S]*?--vms-surface: #ffffff/,
    );
  });

  it('dark theme uses light primary text on dark surfaces (no dark-on-dark contract)', () => {
    const darkMain = themeCss.match(
      /\.admin-layout\[data-theme='dark'\] \.admin-main\s*\{([^}]+)\}/,
    )?.[1] ?? '';
    expect(darkMain).toContain('--vms-text-primary: #f8fafc');
    expect(darkMain).toContain('--vms-surface: #1e293b');
    expect(darkMain).toContain('--vms-page-bg: #0f172a');
    // Primary text must not be the same dark navy as page background
    expect(darkMain).not.toContain('--vms-text-primary: #0f172a');
  });

  it('staff UI provides SectionCard and StatCard primitives', () => {
    expect(staffUiCss).toContain('.section-card');
    expect(staffUiCss).toContain('.stat-card');
    expect(staffUiCss).toContain('.metric-card');
  });

  it('staff UI standardizes tables, forms, badges, and empty states', () => {
    expect(staffUiCss).toContain('.admin-main .admin-table th');
    expect(staffUiCss).toContain('.admin-main input:not([type=\'checkbox\'])');
    expect(staffUiCss).toContain('.admin-main .admin-btn--primary');
    expect(staffUiCss).toContain('.admin-main .empty-state');
    expect(staffUiCss).toContain('.status-badge--pending');
  });

  it('Dashboard uses reference KPI grid and section cards', () => {
    expect(dashboardPage).toContain('className="section-card"');
    expect(dashboardPage).toContain('Visitor Activity');
    expect(dashboardPage).toContain('VisitorActivityChart');
    expect(dashboardPage).toContain('Location Performance');
    expect(dashboardPage).toContain('KpiStatCard');
    expect(dashboardPage).toContain('vms-kpi-strip');
    expect(dashboardPage).toContain('variant="compact"');
    expect(dashboardPage).toContain('vms-quick-actions');
  });

  it('sidebar remains dark navy independent of content theme', () => {
    expect(themeCss).toContain('--vms-sidebar-bg: #0f172a');
    expect(themeCss).toContain('background: var(--vms-sidebar-bg)');
  });
});
