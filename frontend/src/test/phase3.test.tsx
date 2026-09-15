import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ApprovalsPage } from '../pages/approvals/ApprovalsPage';
import { api } from '../services/api';

vi.mock('../services/api', () => ({
  api: {
    approvals: vi.fn(),
    rejectionReasons: vi.fn(),
    approveVisit: vi.fn(),
    rejectVisit: vi.fn(),
    approvalDetail: vi.fn(),
  },
  ApiClientError: class extends Error {
    status = 409;
    code = 'APPROVAL_ALREADY_DECIDED';
  },
}));

const mockItem = {
  id: 1,
  registration_reference: 'VMS-260826-0001',
  status: 'PENDING_APPROVAL',
  visitor_name: 'Rahul Sharma',
  visitor_mobile: '+919999999999',
  visitor_email: 'rahul@test.com',
  company: 'ABC Pvt Ltd',
  visitor_type: 'Business Visitor',
  host_name: 'Amit Kumar',
  site_name: 'Development Main Office',
  site_id: 1,
  purpose: 'Meeting',
  expected_duration_minutes: 120,
  policy_accepted: true,
  submitted_at: new Date().toISOString(),
  approval_history: [],
};

describe('ApprovalsPage', () => {
  beforeEach(() => {
    vi.mocked(api.rejectionReasons).mockResolvedValue([
      { code: 'HOST_UNAVAILABLE', label: 'Host unavailable' },
      { code: 'OTHER', label: 'Other' },
    ]);
    vi.mocked(api.approvals).mockResolvedValue({
      items: [mockItem],
      total: 1,
      limit: 50,
      offset: 0,
      pending_count: 1,
    });
  });

  it('renders approvals page with pending queue', async () => {
    render(
      <BrowserRouter>
        <ApprovalsPage />
      </BrowserRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('Approvals')).toBeInTheDocument();
      expect(screen.getByText('Rahul Sharma')).toBeInTheDocument();
    });
  });

  it('shows pending count in tab', async () => {
    render(
      <BrowserRouter>
        <ApprovalsPage />
      </BrowserRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('(1)')).toBeInTheDocument();
    });
  });
});
