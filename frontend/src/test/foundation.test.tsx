import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { VisitorWelcomePage } from '../pages/visit/VisitorWelcomePage';
import { AdminLayout } from '../layouts/AdminLayout';
import { filterNavByPermissions, hasPermission, NAV_ITEMS } from '../utils/permissions';
import type { UserProfile } from '../types';

const mockGlobalAdmin: UserProfile = {
  id: 1,
  email: 'sheru.bohra@lazypay.in',
  display_name: 'Sheru Bohra',
  role: 'GLOBAL_ADMIN',
  is_owner: true,
  is_active: true,
  permissions: [
    'analytics.dashboard.view',
    'visitor.read',
    'reports.view',
    'reports.export',
    'admins.read',
    'onsite.read',
    'registration.read',
    'approval.read',
    'locations.read',
  ],
  location_ids: [1],
};

describe('permission navigation', () => {
  const globalAdminPerms = [
    'analytics.dashboard.view',
    'visitor.read',
    'reports.view',
    'reports.export',
    'admins.read',
  ];

  const siteAdminPerms = [
    'visitor.read',
    'visitor.checkin',
    'onsite.read',
    'registration.read',
    'approval.read',
    'locations.read',
  ];

  it('filters management nav for SITE_ADMIN but keeps operational dashboard', () => {
    const filtered = filterNavByPermissions(siteAdminPerms);
    const ids = filtered.map((i) => i.id);
    expect(ids).toContain('dashboard');
    expect(ids).not.toContain('reports');
    expect(ids).toContain('visitors');
    expect(ids).toContain('onsite');
  });

  it('includes management nav for GLOBAL_ADMIN', () => {
    const filtered = filterNavByPermissions(globalAdminPerms);
    const ids = filtered.map((i) => i.id);
    expect(ids).toContain('dashboard');
    expect(ids).toContain('reports');
  });

  it('SITE_ADMIN lacks report export permission check', () => {
    expect(hasPermission(siteAdminPerms, 'reports.export')).toBe(false);
    expect(hasPermission(siteAdminPerms, 'analytics.weekly.view')).toBe(false);
  });

  it('GLOBAL_ADMIN has report permissions', () => {
    expect(hasPermission(globalAdminPerms, 'reports.export')).toBe(true);
  });

  it('NAV_ITEMS has all expected modules', () => {
    expect(NAV_ITEMS.length).toBe(19);
  });
});

describe('VisitorWelcomePage', () => {
  it('renders mobile visitor shell', () => {
    render(
      <BrowserRouter>
        <VisitorWelcomePage />
      </BrowserRouter>,
    );
    expect(screen.getByText('Welcome to Visitor Check-In')).toBeInTheDocument();
    expect(screen.getByText('Start Registration')).toBeInTheDocument();
    expect(screen.getByText('Visitor Check-In')).toBeInTheDocument();
  });
});

describe('AdminLayout', () => {
  it('renders admin shell with navigation', () => {
    render(
      <BrowserRouter>
        <Routes>
          <Route element={<AdminLayout user={mockGlobalAdmin} />}>
            <Route index element={<div>Content area</div>} />
          </Route>
        </Routes>
      </BrowserRouter>,
    );
    expect(screen.getByText('Visitor Management')).toBeInTheDocument();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Visitor Operations')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Insights/i }));
    expect(screen.getByText('Reports')).toBeInTheDocument();
    expect(screen.getByText('Content area')).toBeInTheDocument();
  });
});
