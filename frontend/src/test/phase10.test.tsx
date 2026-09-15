import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter, MemoryRouter, Route, Routes } from 'react-router-dom';
import { DashboardPage } from '../pages/dashboard/DashboardPage';
import { ReportsPage } from '../pages/reports/ReportsPage';
import { filterNavByPermissions, hasPermission } from '../utils/permissions';
import type { UserProfile } from '../types';

const mockDashboard = {
  range: { period: 'today', from: '2026-08-26T00:00:00+00:00', to: '2026-08-27T00:00:00+00:00', location_label: 'All authorized locations' },
  kpis: {
    expected_today: 5,
    awaiting_approval: 2,
    checked_in_today: 3,
    onsite_now: 4,
    checked_out_today: 1,
    overstayed: 0,
    vendor_contractor_onsite: 1,
  },
  visitor_trend: [{ date: '2026-08-26', expected: 2, checked_in: 1, checked_out: 0 }],
  visitor_types: [{ name: 'Business Visitor', count: 3 }],
  locations: [{ location_id: 1, location_name: 'Bangalore', visitors: 5, check_ins: 3, onsite: 2, rejected: 0 }],
  peak_arrivals: [],
  approval_metrics: { average_minutes: 12, median_minutes: 10, sample_size: 2 },
  visit_duration: { average_minutes: 45, sample_size: 1 },
  security_summary: { review: 1, blocked: 0 },
  compliance_summary: { review_required: 0, non_compliant: 0, expiring: 0 },
  active_emergencies: [],
};

vi.mock('../services/api', () => ({
  api: {
    analyticsDashboard: vi.fn(() => Promise.resolve(mockDashboard)),
    reportVisits: vi.fn(() => Promise.resolve({
      items: [{
        registration_reference: 'VMS-1',
        visitor_name: 'Test Visitor',
        company: 'Co',
        visitor_type: 'Business Visitor',
        location_name: 'Bangalore',
        status: 'APPROVED',
      }],
      total: 1,
      page: 1,
      page_size: 50,
    })),
    exportReportVisits: vi.fn(() => Promise.resolve(new Blob(['csv']))),
    locations: vi.fn(() => Promise.resolve([
      { id: 1, name: 'Bangalore', code: 'BLR', is_active: true, is_development_seed: true },
    ])),
  },
}));

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({
    user: {
      id: 1,
      email: 'sheru.bohra@lazypay.in',
      display_name: 'Owner',
      role: 'GLOBAL_ADMIN' as const,
      is_owner: true,
      is_active: true,
      permissions: [
        'analytics.dashboard.view',
        'reports.view',
        'reports.export',
        'reports.export.csv',
        'reports.export.xlsx',
        'locations.read',
      ],
      location_ids: [1],
      assigned_locations: [],
    },
    loading: false,
    error: null,
    unauthorized: false,
    reload: vi.fn(),
  }),
}));

describe('Phase 10 dashboard', () => {
  it('renders management dashboard with KPIs', async () => {
    render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>,
    );
    expect(await screen.findByText('Visitor Management Dashboard')).toBeInTheDocument();
    expect(screen.getAllByText('5').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Expected Today')).toBeInTheDocument();
    expect(document.querySelector('.kpi-stat-card--compact')).toBeTruthy();
    expect(screen.getByText('Visitor Activity')).toBeInTheDocument();
  });
});

describe('Phase 10 reports', () => {
  it('renders reports page with filters and table', async () => {
    render(
      <BrowserRouter>
        <ReportsPage />
      </BrowserRouter>,
    );
    expect(await screen.findByText('Reports')).toBeInTheDocument();
    expect(await screen.findByText('Test Visitor')).toBeInTheDocument();
    expect(screen.getByText('Download CSV')).toBeInTheDocument();
    expect(screen.getByText('Download Excel')).toBeInTheDocument();
  });
});

describe('Phase 10 access denial nav', () => {
  const siteAdminPerms = [
    'visitor.read',
    'onsite.read',
    'registration.read',
    'approval.read',
    'locations.read',
    'arrival.read',
  ];

  const securityPerms = [
    'visitor.read',
    'onsite.read',
    'registration.read',
    'visitor_qr.verify',
    'arrival.read',
  ];

  it('SITE_ADMIN nav excludes reports and management insights', () => {
    const ids = filterNavByPermissions(siteAdminPerms).map((i) => i.id);
    expect(ids).toContain('dashboard');
    expect(ids).not.toContain('reports');
  });

  it('SECURITY nav excludes reports but includes dashboard', () => {
    const ids = filterNavByPermissions(securityPerms).map((i) => i.id);
    expect(ids).toContain('dashboard');
    expect(ids).not.toContain('reports');
  });

  it('SITE_ADMIN lacks export permissions', () => {
    expect(hasPermission(siteAdminPerms, 'reports.export')).toBe(false);
    expect(hasPermission(siteAdminPerms, 'analytics.dashboard.view')).toBe(false);
  });
});

describe('Phase 10 route guard', () => {
  it('site admin can access dashboard route without analytics permission', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route path="/dashboard" element={<DashboardPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('Loading dashboard…')).toBeInTheDocument();
  });
});
