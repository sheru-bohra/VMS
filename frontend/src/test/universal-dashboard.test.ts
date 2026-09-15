import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { roleHomePath } from '../config/auth';
import { filterDashboardNav, filterNavByPermissions } from '../utils/permissions';
import { isLandingPageAllowed, getDefaultLandingPath } from '../utils/userPreferences';
import { DASHBOARD_NAV } from '../utils/navigationConfig';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const appTsx = readFileSync(resolve(root, 'app/App.tsx'), 'utf8');

const SITE_ADMIN_PERMS = [
  'visitor.read',
  'onsite.read',
  'arrival.read',
  'approval.read',
  'locations.read',
];

const SECURITY_PERMS = [
  'visitor.read',
  'onsite.read',
  'arrival.read',
  'watchlist.read',
  'security_screening.read',
];

describe('universal role-aware dashboard access', () => {
  it('dashboard nav is visible without analytics.dashboard.view', () => {
    expect(filterDashboardNav(SITE_ADMIN_PERMS)).toEqual(DASHBOARD_NAV);
    expect(filterDashboardNav(SECURITY_PERMS)).toEqual(DASHBOARD_NAV);
    const ids = filterNavByPermissions(SITE_ADMIN_PERMS).map((i) => i.id);
    expect(ids).toContain('dashboard');
  });

  it('default landing is dashboard for all staff roles', () => {
    expect(roleHomePath('GLOBAL_ADMIN')).toBe('/dashboard');
    expect(roleHomePath('HEAD_ADMIN')).toBe('/dashboard');
    expect(roleHomePath('SITE_ADMIN')).toBe('/dashboard');
    expect(roleHomePath('SECURITY')).toBe('/dashboard');
    expect(getDefaultLandingPath(1, SITE_ADMIN_PERMS, 'SITE_ADMIN')).toBe('/dashboard');
    expect(getDefaultLandingPath(2, SECURITY_PERMS, 'SECURITY')).toBe('/dashboard');
  });

  it('dashboard landing preference allowed for site admin and security', () => {
    expect(isLandingPageAllowed('/dashboard', SITE_ADMIN_PERMS)).toBe(true);
    expect(isLandingPageAllowed('/dashboard', SECURITY_PERMS)).toBe(true);
    expect(isLandingPageAllowed('/reports', SITE_ADMIN_PERMS)).toBe(false);
    expect(isLandingPageAllowed('/reports', SECURITY_PERMS)).toBe(false);
  });

  it('dashboard route is not wrapped in analytics permission guard', () => {
    expect(appTsx).toContain('<Route path="dashboard" element={<DashboardPage />} />');
    expect(appTsx).not.toContain('permission="analytics.dashboard.view"');
  });
});
