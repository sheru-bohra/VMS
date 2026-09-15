import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Sidebar } from '../components/admin/Sidebar';
import { PreferencesProvider } from '../contexts/PreferencesContext';
import {
  DASHBOARD_NAV,
  NAV_GROUPS,
  findActiveGroupId,
  isNavChildActive,
} from '../utils/navigationConfig';
import {
  filterNavByPermissions,
  filterNavGroupsByPermissions,
  NAV_ITEMS,
} from '../utils/permissions';
import {
  buildInitialOpenGroupId,
  loadOpenGroupId,
  saveOpenGroupId,
  sidebarGroupsStorageKey,
} from '../utils/sidebarGroups';
import type { UserProfile } from '../types';

const GLOBAL_ADMIN_PERMS = [
  'analytics.dashboard.view',
  'visitor.read',
  'arrival.read',
  'onsite.read',
  'invitation.read',
  'invitation.create',
  'registration.read',
  'visitor_qr.verify',
  'approval.read',
  'watchlist.read',
  'security_screening.read',
  'emergency.read',
  'access.read',
  'vendor_company.read',
  'reports.view',
  'ai.copilot.use',
  'admins.read',
  'locations.read',
  'privacy.retention.read',
  'access.config.read',
  'operations.readiness.read',
];

const HEAD_ADMIN_PERMS = [
  'analytics.dashboard.view',
  'visitor.read',
  'arrival.read',
  'onsite.read',
  'invitation.read',
  'invitation.create',
  'registration.read',
  'approval.read',
  'watchlist.read',
  'security_screening.read',
  'emergency.read',
  'vendor_company.read',
  'reports.view',
  'admins.read',
  'locations.read',
];

const SITE_ADMIN_PERMS = [
  'visitor.read',
  'visitor.checkin',
  'onsite.read',
  'registration.read',
  'approval.read',
  'locations.read',
  'arrival.read',
];

const SECURITY_PERMS = [
  'visitor.read',
  'onsite.read',
  'registration.read',
  'visitor_qr.verify',
  'arrival.read',
  'watchlist.read',
  'security_screening.read',
  'emergency.read',
];

const mockUser: UserProfile = {
  id: 42,
  email: 'test@vms.local',
  display_name: 'Test User',
  role: 'GLOBAL_ADMIN',
  is_owner: false,
  is_active: true,
  permissions: GLOBAL_ADMIN_PERMS,
  location_ids: [1],
  assigned_locations: [],
};

function renderSidebar(initialPath = '/dashboard', permissions = GLOBAL_ADMIN_PERMS) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <PreferencesProvider user={{ ...mockUser, permissions }}>
        <Sidebar userId={42} permissions={permissions} collapsed={false} onToggle={() => {}} />
      </PreferencesProvider>
    </MemoryRouter>,
  );
}

describe('sidebar navigation config', () => {
  it('NAV_ITEMS flat list preserves all routes including Register Visitor', () => {
    expect(NAV_ITEMS.length).toBe(19);
  });

  it('does not include Scan Visitor QR nav item', () => {
    expect(NAV_ITEMS.some((item) => item.label === 'Scan Visitor QR')).toBe(false);
    expect(NAV_ITEMS.some((item) => item.path === '/scan')).toBe(false);
  });

  it('defines five collapsible groups plus dashboard', () => {
    expect(NAV_GROUPS.length).toBe(5);
    expect(DASHBOARD_NAV.id).toBe('dashboard');
  });

  it('filters unauthorized children and hides empty groups', () => {
    const groups = filterNavGroupsByPermissions(SITE_ADMIN_PERMS);
    const ids = groups.map((g) => g.id);
    expect(ids).toContain('visitor-operations');
    expect(ids).not.toContain('insights');
    expect(ids).toContain('system-administration');
    const adminGroup = groups.find((g) => g.id === 'system-administration');
    expect(adminGroup?.children.map((c) => c.id)).toEqual(['locations']);
    groups.forEach((g) => expect(g.children.length).toBeGreaterThan(0));
  });

  it('SECURITY sees operational groups without insights or system admin', () => {
    const groups = filterNavGroupsByPermissions(SECURITY_PERMS);
    const ids = groups.map((g) => g.id);
    expect(ids).toContain('visitor-operations');
    expect(ids).toContain('security-access');
    expect(ids).not.toContain('insights');
    expect(ids).not.toContain('system-administration');
    expect(filterNavByPermissions(SECURITY_PERMS).map((i) => i.id)).not.toContain('reports');
  });

  it('GLOBAL_ADMIN sees all groups when fully permitted', () => {
    const groups = filterNavGroupsByPermissions(GLOBAL_ADMIN_PERMS);
    expect(groups.map((g) => g.id)).toEqual([
      'visitor-operations',
      'security-access',
      'vendors-compliance',
      'insights',
      'system-administration',
    ]);
  });
});

describe('route active matching', () => {
  it('auto-expands parent group for nested administration routes', () => {
    const groups = filterNavGroupsByPermissions(GLOBAL_ADMIN_PERMS);
    expect(findActiveGroupId('/administration/privacy-security', groups)).toBe('system-administration');
    expect(isNavChildActive('/administration/privacy-security', NAV_GROUPS[4].children[2])).toBe(true);
    expect(isNavChildActive('/administration', NAV_GROUPS[4].children[0])).toBe(true);
    expect(isNavChildActive('/administration/users', NAV_GROUPS[4].children[0])).toBe(true);
  });

  it('matches vendor alias paths', () => {
    const vendor = NAV_GROUPS.find((g) => g.id === 'vendors-compliance')!.children[0];
    expect(isNavChildActive('/vendors-contractors/1', vendor)).toBe(true);
  });
});

describe('sidebar group persistence', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('persists single open group id per user', () => {
    saveOpenGroupId(42, 'security-access');
    expect(loadOpenGroupId(42)).toBe('security-access');
    expect(localStorage.getItem(sidebarGroupsStorageKey(42))).toBe('"security-access"');
  });

  it('defaults to active route group on first load', () => {
    const openId = buildInitialOpenGroupId(99, 'visitor-operations');
    expect(openId).toBe('visitor-operations');
  });

  it('defaults to null on top-level routes without active group', () => {
    expect(buildInitialOpenGroupId(99)).toBeNull();
  });
});

describe('Sidebar UI', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders dashboard as direct item and grouped sections', () => {
    renderSidebar();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Register Visitor')).toBeInTheDocument();
    expect(screen.getByText('Visitor Operations')).toBeInTheDocument();
    expect(screen.getByText('Security & Access')).toBeInTheDocument();
    expect(screen.getByText('System Administration')).toBeInTheDocument();
    expect(screen.queryByText('Emergency Roll-Call')).not.toBeInTheDocument();
    expect(screen.queryByText('Scan Visitor QR')).not.toBeInTheDocument();
    expect(screen.queryByText('Scan Visitor QR')).not.toBeInTheDocument();
  });

  it('expands active group on approvals route', () => {
    renderSidebar('/approvals');
    expect(screen.getByText('Approvals')).toBeVisible();
    expect(screen.getByRole('button', { name: /Visitor Operations/i })).toHaveAttribute('aria-expanded', 'true');
  });

  it('highlights active child on security review route', () => {
    renderSidebar('/security-review', GLOBAL_ADMIN_PERMS);
    const link = screen.getByRole('link', { name: 'Security Review' });
    expect(link.className).toContain('admin-sidebar__link--active');
  });

  it('accordion opens only one group at a time', () => {
    renderSidebar();
    const visitorBtn = screen.getByRole('button', { name: /Visitor Operations/i });
    const securityBtn = screen.getByRole('button', { name: /Security & Access/i });
    fireEvent.click(visitorBtn);
    expect(visitorBtn).toHaveAttribute('aria-expanded', 'true');
    fireEvent.click(securityBtn);
    expect(securityBtn).toHaveAttribute('aria-expanded', 'true');
    expect(visitorBtn).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getByText('Watchlist')).toBeVisible();
  });

  it('accordion closes third group when opening another', () => {
    renderSidebar();
    const securityBtn = screen.getByRole('button', { name: /Security & Access/i });
    const vendorsBtn = screen.getByRole('button', { name: /Vendors & Compliance/i });
    fireEvent.click(securityBtn);
    expect(securityBtn).toHaveAttribute('aria-expanded', 'true');
    fireEvent.click(vendorsBtn);
    expect(vendorsBtn).toHaveAttribute('aria-expanded', 'true');
    expect(securityBtn).toHaveAttribute('aria-expanded', 'false');
  });

  it('toggles closed when clicking the currently open group', () => {
    renderSidebar();
    const visitorBtn = screen.getByRole('button', { name: /Visitor Operations/i });
    fireEvent.click(visitorBtn);
    expect(visitorBtn).toHaveAttribute('aria-expanded', 'true');
    fireEvent.click(visitorBtn);
    expect(visitorBtn).toHaveAttribute('aria-expanded', 'false');
  });

  it('opens Security & Access for /watchlist route on load', () => {
    renderSidebar('/watchlist', GLOBAL_ADMIN_PERMS);
    expect(screen.getByRole('button', { name: /Security & Access/i })).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('button', { name: /Visitor Operations/i })).toHaveAttribute('aria-expanded', 'false');
  });

  it('uses colored icon tone classes', () => {
    renderSidebar();
    expect(document.querySelector('.nav-icon--tone-blue')).toBeTruthy();
    expect(document.querySelector('.nav-icon--tone-indigo')).toBeTruthy();
  });

  it('SITE_ADMIN does not show empty insights group', () => {
    renderSidebar('/visitors', SITE_ADMIN_PERMS);
    expect(screen.queryByText('Insights')).not.toBeInTheDocument();
    expect(screen.queryByText('Reports')).not.toBeInTheDocument();
  });
});

describe('sidebar accordion by role', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('GLOBAL_ADMIN accordion keeps one group open', () => {
    renderSidebar('/dashboard', GLOBAL_ADMIN_PERMS);
    const visitorBtn = screen.getByRole('button', { name: /Visitor Operations/i });
    const insightsBtn = screen.getByRole('button', { name: /Insights/i });
    fireEvent.click(visitorBtn);
    fireEvent.click(insightsBtn);
    expect(insightsBtn).toHaveAttribute('aria-expanded', 'true');
    expect(visitorBtn).toHaveAttribute('aria-expanded', 'false');
  });

  it('HEAD_ADMIN accordion works with visible groups', () => {
    renderSidebar('/dashboard', HEAD_ADMIN_PERMS);
    const visitorBtn = screen.getByRole('button', { name: /Visitor Operations/i });
    const securityBtn = screen.getByRole('button', { name: /Security & Access/i });
    fireEvent.click(visitorBtn);
    fireEvent.click(securityBtn);
    expect(securityBtn).toHaveAttribute('aria-expanded', 'true');
    expect(visitorBtn).toHaveAttribute('aria-expanded', 'false');
  });

  it('SITE_ADMIN accordion works with visible groups', () => {
    renderSidebar('/visitors', SITE_ADMIN_PERMS);
    const visitorBtn = screen.getByRole('button', { name: /Visitor Operations/i });
    const adminBtn = screen.getByRole('button', { name: /System Administration/i });
    fireEvent.click(visitorBtn);
    fireEvent.click(adminBtn);
    expect(adminBtn).toHaveAttribute('aria-expanded', 'true');
    expect(visitorBtn).toHaveAttribute('aria-expanded', 'false');
  });

  it('SECURITY accordion works with visible groups', () => {
    renderSidebar('/dashboard', SECURITY_PERMS);
    const visitorBtn = screen.getByRole('button', { name: /Visitor Operations/i });
    const securityBtn = screen.getByRole('button', { name: /Security & Access/i });
    fireEvent.click(visitorBtn);
    fireEvent.click(securityBtn);
    expect(securityBtn).toHaveAttribute('aria-expanded', 'true');
    expect(visitorBtn).toHaveAttribute('aria-expanded', 'false');
  });
});

describe('sidebar scroll CSS', () => {
  it('preserves independent sidebar scroll region', async () => {
    const { readFileSync } = await import('node:fs');
    const { dirname, resolve } = await import('node:path');
    const { fileURLToPath } = await import('node:url');
    const adminCss = readFileSync(
      resolve(dirname(fileURLToPath(import.meta.url)), '../styles/admin.css'),
      'utf8',
    );
    expect(adminCss).toMatch(/\.admin-sidebar__nav\s*\{[^}]*overflow-y:\s*auto/);
    expect(adminCss).toContain('.admin-sidebar__group-btn');
    expect(adminCss).toContain('.nav-icon--tone-blue');
  });
});
