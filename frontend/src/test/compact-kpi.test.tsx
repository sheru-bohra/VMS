import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { DashboardPage } from '../pages/dashboard/DashboardPage';
import { triggerOperationalRefresh } from '../utils/operationalRefreshEvents';

const mockKpis = {
  expected_today: 3,
  awaiting_approval: 2,
  checked_in_today: 5,
  onsite_now: 4,
  checked_out_today: 1,
  overstayed: 1,
  vendor_contractor_onsite: 2,
};

const mockDashboard = {
  range: {
    period: 'today',
    from: '2026-08-26T00:00:00+00:00',
    to: '2026-08-27T00:00:00+00:00',
    location_label: 'All authorized locations',
  },
  kpis: mockKpis,
  visitor_trend: [],
  visitor_types: [],
  locations: [],
  peak_arrivals: [],
  approval_metrics: { average_minutes: 0, median_minutes: 0, sample_size: 0 },
  visit_duration: { average_minutes: 0, sample_size: 0 },
  security_summary: { review: 0, blocked: 0 },
  compliance_summary: { review_required: 0, non_compliant: 0, expiring: 0 },
  active_emergencies: [],
};

const analyticsDashboard = vi.fn(() => Promise.resolve(mockDashboard));
const onsiteVisitors = vi.fn(() => Promise.resolve({ items: [], total: 0, limit: 5, offset: 0 }));

vi.mock('../services/api', () => ({
  api: {
    analyticsDashboard: (...args: unknown[]) => analyticsDashboard(...args),
    onsiteVisitors: (...args: unknown[]) => onsiteVisitors(...args),
    locations: vi.fn(() => Promise.resolve([])),
  },
}));

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({
    user: {
      id: 1,
      email: 'admin@vms.local',
      display_name: 'Admin',
      role: 'GLOBAL_ADMIN' as const,
      is_owner: true,
      is_active: true,
      permissions: ['analytics.dashboard.view', 'onsite.read', 'locations.read'],
      location_ids: [1],
      assigned_locations: [],
    },
    loading: false,
    error: null,
    unauthorized: false,
    reload: vi.fn(),
  }),
}));

describe('Dashboard compact KPI strip', () => {
  beforeEach(() => {
    analyticsDashboard.mockClear();
    onsiteVisitors.mockClear();
  });

  it('renders all seven compact KPI cards with API values', async () => {
    const { container } = render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>,
    );

    expect(await screen.findByText('Visitor Management Dashboard')).toBeInTheDocument();
    expect(container.querySelectorAll('.kpi-stat-card--compact')).toHaveLength(7);
    expect(container.querySelector('.vms-kpi-strip')).toBeTruthy();

    expect(screen.getByText('Expected Today')).toBeInTheDocument();
    expect(screen.getByText('Awaiting Approval')).toBeInTheDocument();
    expect(screen.getByText('Checked In Today')).toBeInTheDocument();
    expect(screen.getByText('Onsite Now')).toBeInTheDocument();
    expect(screen.getByText('Checked Out Today')).toBeInTheDocument();
    expect(screen.getByText('Overstayed')).toBeInTheDocument();
    expect(screen.getByText('Vendor/Contractor Onsite')).toBeInTheDocument();

    const strip = container.querySelector('.vms-kpi-strip');
    expect(strip).toBeTruthy();
    const values = strip!.querySelectorAll('.kpi-stat-card__value');
    expect(Array.from(values, (el) => el.textContent)).toEqual(['3', '2', '5', '4', '1', '1', '2']);
  });

  it('passes period and location filters to dashboard aggregate API', async () => {
    render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>,
    );
    await screen.findByText('Visitor Management Dashboard');

    expect(analyticsDashboard).toHaveBeenCalled();
    const firstCall = analyticsDashboard.mock.calls[0][0];
    expect(firstCall).toEqual({ period: 'today', location_id: undefined });
  });

  it('manual Refresh triggers dashboard refetch', async () => {
    render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>,
    );
    await screen.findByText('Visitor Management Dashboard');
    const initialCalls = analyticsDashboard.mock.calls.length;

    screen.getByRole('button', { name: 'Refresh' }).click();
    await vi.waitFor(() => expect(analyticsDashboard.mock.calls.length).toBeGreaterThan(initialCalls));
  });

  it('operational refresh event triggers background dashboard refetch', async () => {
    render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>,
    );
    await screen.findByText('Visitor Management Dashboard');
    const before = analyticsDashboard.mock.calls.length;

    triggerOperationalRefresh();
    await vi.waitFor(() => expect(analyticsDashboard.mock.calls.length).toBeGreaterThan(before));
  });

  it('uses single aggregate API for KPIs, not per-card requests', async () => {
    render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>,
    );
    await screen.findByText('Visitor Management Dashboard');
    const dashboardCalls = analyticsDashboard.mock.calls.length;
    expect(dashboardCalls).toBeGreaterThan(0);
    expect(dashboardCalls).toBeLessThanOrEqual(2);
  });
});
