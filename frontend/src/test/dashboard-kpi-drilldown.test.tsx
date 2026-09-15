import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { DashboardPage } from '../pages/dashboard/DashboardPage';
import { buildKpiNavigationPath, shouldUseKpiModal, DASHBOARD_KPIS } from '../pages/dashboard/dashboardKpi';
import { hasPermission } from '../utils/permissions';

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

const mockKpis = {
  expected_today: 2,
  awaiting_approval: 5,
  checked_in_today: 2,
  onsite_now: 1,
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
const onsiteVisitors = vi.fn(() => Promise.resolve({ items: [], total: 0, limit: 5, offset: 0, onsite_count: 0 }));
const dashboardKpiDrillDown = vi.fn(() => Promise.resolve({
  items: [{
    id: 1,
    visitor_name: 'Jane Doe',
    company: 'Acme',
    host_name: 'Host',
    site_name: 'Bangalore',
    status: 'ONSITE',
    checked_in_at: '2026-08-28T10:00:00+00:00',
  }],
  total: 1,
  limit: 100,
  offset: 0,
}));

vi.mock('../services/api', () => ({
  api: {
    analyticsDashboard: (...args: unknown[]) => analyticsDashboard(...args),
    onsiteVisitors: (...args: unknown[]) => onsiteVisitors(...args),
    dashboardKpiDrillDown: (...args: unknown[]) => dashboardKpiDrillDown(...args),
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
      permissions: [
        'analytics.dashboard.view',
        'onsite.read',
        'locations.read',
        'invitation.create',
        'checkin.perform',
        'arrival.read',
      ],
      location_ids: [1, 2],
      assigned_locations: [{ id: 1, name: 'Bangalore' }, { id: 2, name: 'Mumbai' }],
    },
    loading: false,
    error: null,
    unauthorized: false,
    reload: vi.fn(),
  }),
}));

describe('dashboard KPI drill-down helpers', () => {
  it('builds navigation paths with location and approval status', () => {
    const awaiting = DASHBOARD_KPIS.find((kpi) => kpi.id === 'awaiting_approval')!;
    expect(buildKpiNavigationPath(awaiting, 3)).toBe('/approvals?site=3&status=PENDING_APPROVAL');
    expect(buildKpiNavigationPath(DASHBOARD_KPIS[0])).toBe('/expected-today');
  });

  it('uses modal when KPI requires it or location filter is active for approvals', () => {
    const checkedIn = DASHBOARD_KPIS.find((kpi) => kpi.id === 'checked_in_today')!;
    const awaiting = DASHBOARD_KPIS.find((kpi) => kpi.id === 'awaiting_approval')!;
    expect(shouldUseKpiModal(checkedIn)).toBe(true);
    expect(shouldUseKpiModal(awaiting)).toBe(false);
    expect(shouldUseKpiModal(awaiting, 2)).toBe(true);
  });
});

describe('Dashboard KPI interactions', () => {
  beforeEach(() => {
    mockNavigate.mockReset();
    dashboardKpiDrillDown.mockClear();
  });

  it('renders seven interactive KPI cards', async () => {
    const { container } = render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>,
    );
    await screen.findByText('Visitor Management Dashboard');
    expect(container.querySelectorAll('.kpi-stat-card--interactive')).toHaveLength(7);
  });

  it('links Expected Today KPI to the expected-today route', async () => {
    render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>,
    );
    await screen.findByText('Visitor Management Dashboard');
    expect(screen.getByRole('link', { name: /View today's expected visitors/i })).toHaveAttribute('href', '/expected-today');
  });

  it('links Onsite Now KPI to the onsite-now route', async () => {
    render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>,
    );
    await screen.findByText('Visitor Management Dashboard');
    expect(screen.getByRole('link', { name: /View visitors currently onsite/i })).toHaveAttribute('href', '/onsite-now');
  });

  it('opens drill-down modal for Checked In Today', async () => {
    render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>,
    );
    await screen.findByText('Visitor Management Dashboard');
    fireEvent.click(screen.getByRole('button', { name: /View visitors checked in today/i }));
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Checked In Today (2)')).toBeInTheDocument();
    expect(dashboardKpiDrillDown).toHaveBeenCalledWith('checked_in_today', { location_id: undefined, limit: 100 });
  });

  it('shows Check In quick action for authorized users', async () => {
    render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>,
    );
    await screen.findByText('Visitor Management Dashboard');
    const checkIn = screen.getByRole('link', { name: 'Check In' });
    expect(checkIn).toHaveAttribute('href', '/expected-today');
    const actions = screen.getAllByRole('link').filter((el) => el.classList.contains('vms-quick-action'));
    expect(actions.map((el) => el.textContent?.trim())).toEqual([
      'Register / Invite Visitor',
      'Check In',
      'Check Out',
    ]);
  });

  it('supports keyboard activation on modal KPI cards', async () => {
    render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>,
    );
    await screen.findByText('Visitor Management Dashboard');
    const overstayButton = screen.getByRole('button', { name: /View overstayed visitors/i });
    overstayButton.focus();
    fireEvent.keyDown(overstayButton, { key: 'Enter' });
    fireEvent.click(overstayButton);
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
  });
});

describe('Check In quick action permissions', () => {
  it('requires checkin.perform permission', () => {
    expect(hasPermission(['checkin.perform'], 'checkin.perform')).toBe(true);
    expect(hasPermission(['analytics.dashboard.view', 'onsite.read'], 'checkin.perform')).toBe(false);
  });
});
