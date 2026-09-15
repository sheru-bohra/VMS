import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ExpectedTodayPage } from '../pages/expected-today/ExpectedTodayPage';
import { OnsiteNowPage } from '../pages/onsite/OnsiteNowPage';
import { api } from '../services/api';

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({
    user: {
      id: 1,
      email: 'test@vms.local',
      display_name: 'Test',
      role: 'GLOBAL_ADMIN',
      is_owner: false,
      is_active: true,
      permissions: ['arrival.read', 'onsite.read', 'locations.read'],
      location_ids: [1],
      assigned_locations: [{ id: 1, name: 'Bangalore Office', code: 'BLR', city: 'Bangalore' }],
    },
    loading: false,
    error: null,
    unauthorized: false,
    reload: vi.fn(),
  }),
}));

vi.mock('../services/api', () => ({
  api: {
    expectedToday: vi.fn(),
    onsiteVisitors: vi.fn(),
    locations: vi.fn(),
    arriveVisit: vi.fn(),
    checkInVisit: vi.fn(),
    checkOutVisit: vi.fn(),
  },
  ApiClientError: class extends Error {
    status = 409;
    code = 'INVALID_VISIT_STATE';
  },
}));

const mockVisit = {
  id: 1,
  registration_reference: 'VMS-260826-0001',
  status: 'APPROVED',
  visitor_name: 'Rahul Sharma',
  visitor_mobile: '+919999999999',
  visitor_email: 'rahul@test.com',
  company: 'ABC Ltd',
  visitor_type: 'Business Visitor',
  host_name: 'Amit Kumar',
  site_name: 'Bangalore Office',
  site_id: 1,
  site_city: 'Bangalore',
  purpose: 'Meeting',
  expected_duration_minutes: 120,
  policy_accepted: true,
  submitted_at: new Date().toISOString(),
  approval_history: [],
};

describe('Phase 4 operational pages', () => {
  beforeEach(() => {
    vi.mocked(api.locations).mockResolvedValue([
      {
        id: 1,
        name: 'Bangalore Office',
        code: 'BLR',
        city: 'Bangalore',
        is_active: true,
        is_development_seed: false,
      },
    ]);
    vi.mocked(api.expectedToday).mockResolvedValue({
      items: [mockVisit],
      total: 1,
      limit: 50,
      offset: 0,
    });
    vi.mocked(api.onsiteVisitors).mockResolvedValue({
      items: [{ ...mockVisit, status: 'ONSITE', checked_in_at: new Date().toISOString() }],
      total: 1,
      limit: 50,
      offset: 0,
      onsite_count: 1,
    });
  });

  it('Expected Today page renders queue', async () => {
    render(
      <BrowserRouter>
        <ExpectedTodayPage />
      </BrowserRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('Expected Today')).toBeInTheDocument();
      expect(screen.getByText('Rahul Sharma')).toBeInTheDocument();
    });
  });

  it('Onsite Now page renders with count', async () => {
    render(
      <BrowserRouter>
        <OnsiteNowPage />
      </BrowserRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('Onsite Now')).toBeInTheDocument();
      expect(screen.getByText(/1 visitor onsite/)).toBeInTheDocument();
    });
  });
});
