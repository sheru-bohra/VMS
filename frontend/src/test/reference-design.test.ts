import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const dashboardPage = readFileSync(resolve(root, 'pages/dashboard/DashboardPage.tsx'), 'utf8');
const dashboardKpi = readFileSync(resolve(root, 'pages/dashboard/dashboardKpi.ts'), 'utf8');
const attention = readFileSync(resolve(root, 'components/shell/dashboardAttention.ts'), 'utf8');
const sidebar = readFileSync(resolve(root, 'components/admin/Sidebar.tsx'), 'utf8');
const referenceShell = readFileSync(resolve(root, 'styles/vms-reference-shell.css'), 'utf8');

const REFERENCE_SAMPLE_NAMES = [
  'Kavya Shetty',
  'Mohan Lal',
  'Indira Pillai',
  'XYZ Ltd',
  'ABC Corp',
  'Laxman Pande',
  'Om Prakash',
];

describe('Toqan reference design adaptation', () => {
  it('does not copy reference screenshot sample names into dashboard sources', () => {
    const sources = [dashboardPage, attention, sidebar, referenceShell].join('\n');
    for (const name of REFERENCE_SAMPLE_NAMES) {
      expect(sources).not.toContain(name);
    }
  });

  it('dashboard maps quick actions to existing routes', () => {
    expect(dashboardPage).toContain('/register-visitor');
    expect(dashboardPage).toContain('/expected-today');
    expect(dashboardPage).toContain('/onsite-now');
    expect(dashboardPage).toContain('Check In');
    expect(dashboardPage).not.toContain("href: '/scan'");
  });

  it('dashboard preserves authoritative KPI labels', () => {
    const kpiSources = `${dashboardPage}\n${dashboardKpi}`;
    expect(kpiSources).toContain('Expected Today');
    expect(kpiSources).toContain('Awaiting Approval');
    expect(kpiSources).toContain('Checked In Today');
    expect(kpiSources).toContain('Onsite Now');
    expect(kpiSources).toContain('Checked Out Today');
    expect(kpiSources).toContain('Overstayed');
    expect(kpiSources).toContain('Vendor/Contractor Onsite');
  });

  it('attention banner uses real dashboard data only', () => {
    expect(attention).toContain('buildDashboardAttention');
    expect(attention).not.toContain('unread notifications');
    expect(dashboardPage).toContain('buildDashboardAttention');
    expect(dashboardPage).not.toMatch(/You have \d+ unread/);
  });

  it('sidebar keeps grouped collapsible navigation structure', () => {
    expect(sidebar).toContain('NavGroupSection');
    expect(sidebar).toContain('filterNavGroupsByPermissions');
    expect(sidebar).toContain('filterRegisterVisitorNav');
    expect(sidebar).not.toMatch(/Self-Service Portal/);
  });

  it('reference shell uses PayU brand accent for active nav, not reference red', () => {
    expect(referenceShell).toContain('--vms-brand-accent: #00a36c');
    expect(referenceShell).toContain('admin-sidebar__link--active');
    expect(referenceShell).not.toMatch(/admin-sidebar__link--active[\s\S]*#ef4444/);
  });

  it('dashboard page guards null user before reading permissions', () => {
    expect(dashboardPage).toContain('authLoading');
    expect(dashboardPage).toContain('!user');
  });
});
