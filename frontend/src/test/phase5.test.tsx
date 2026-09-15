import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { InvitationsPage } from '../pages/invitations/InvitationsPage';
import { api } from '../services/api';

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({
    user: {
      permissions: ['invitation.read', 'invitation.create', 'visitor_qr.verify'],
      assigned_locations: [],
    },
    loading: false,
  }),
}));

vi.mock('../services/api', () => ({
  api: {
    invitations: vi.fn(),
    verifyVisitorQr: vi.fn(),
    arriveVisit: vi.fn(),
    checkInVisit: vi.fn(),
  },
  ApiClientError: class extends Error { status = 403; code = 'forbidden'; },
}));

describe('Phase 5 pages', () => {
  beforeEach(() => {
    vi.mocked(api.invitations).mockResolvedValue({
      items: [{
        id: 1,
        registration_reference: 'VMS-260826-0001',
        status: 'APPROVED',
        source: 'advance_registration',
        visitor_name: 'Rahul Sharma',
        visitor_mobile: null,
        visitor_email: null,
        company: 'ABC Ltd',
        visitor_type: 'Business',
        host_name: 'Amit',
        site_name: 'Bangalore Office',
        site_id: 1,
        purpose: 'Meeting',
        expected_duration_minutes: 60,
        scheduled_start: new Date().toISOString(),
        scheduled_end: null,
        submitted_at: new Date().toISOString(),
        invitation_status: 'ACTIVE',
        has_active_invitation: true,
        approval_history: [],
      }],
      total: 1,
      limit: 50,
      offset: 0,
    });
  });

  it('Invitations page renders', async () => {
    render(<BrowserRouter><InvitationsPage /></BrowserRouter>);
    await waitFor(() => {
      expect(screen.getByText('Invitations')).toBeInTheDocument();
      expect(screen.getByText('Rahul Sharma')).toBeInTheDocument();
    });
  });
});
