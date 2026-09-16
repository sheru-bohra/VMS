import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AccessBadgesAdminPage } from '../pages/administration/AccessBadgesAdminPage';
import { AccessOperationsPage } from '../pages/access-operations/AccessOperationsPage';

const globalAdmin = {
  id: 1,
  email: 'admin@test.com',
  role: 'GLOBAL_ADMIN',
  permissions: ['access.config.read', 'access.config.manage', 'badge.printer.config.manage', 'access.read', 'access.retry'],
  is_owner: true,
  is_active: true,
  location_ids: [],
  assigned_locations: [],
};

vi.mock('../services/api', () => ({
  api: {
    me: vi.fn(),
    locations: vi.fn().mockResolvedValue([{ id: 1, name: 'Bangalore Office', code: 'BLR', is_active: true }]),
    visitorTypes: vi.fn().mockResolvedValue([{ id: 1, name: 'Business Visitor', code: 'BUSINESS' }]),
    accessProfiles: vi.fn(),
    accessProfileMappings: vi.fn(),
    badgePrinters: vi.fn(),
    accessLocationConfigs: vi.fn(),
    createAccessProfile: vi.fn(),
    updateAccessProfile: vi.fn(),
    deactivateAccessProfile: vi.fn(),
    createAccessProfileMapping: vi.fn(),
    updateAccessProfileMapping: vi.fn(),
    createBadgePrinter: vi.fn(),
    updateBadgePrinter: vi.fn(),
    accessCredentials: vi.fn(),
    badgePrintJobs: vi.fn(),
    physicalIntegrationStatus: vi.fn(),
    retryAccessCredential: vi.fn(),
  },
}));

import { api } from '../services/api';

describe('Phase 14.1 Access Profile CRUD UI', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.me).mockResolvedValue(globalAdmin);
    vi.mocked(api.accessProfiles).mockResolvedValue([]);
    vi.mocked(api.accessProfileMappings).mockResolvedValue([]);
    vi.mocked(api.badgePrinters).mockResolvedValue([]);
    vi.mocked(api.accessLocationConfigs).mockResolvedValue([]);
    vi.mocked(api.createAccessProfile).mockResolvedValue({
      id: 2,
      location_id: 1,
      name: 'VIP Visitor',
      provider_external_profile_ref: 'VIP',
      is_active: true,
    });
  });

  it('creates access profile from form', async () => {
    render(
      <BrowserRouter>
        <AccessBadgesAdminPage />
      </BrowserRouter>,
    );
    await waitFor(() => expect(screen.getByText('Access & Badge Administration')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Create profile'));
    await waitFor(() => expect(screen.getByText('Create Access Profile')).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText('Profile name'), { target: { value: 'VIP Visitor' } });
    fireEvent.change(screen.getByLabelText('Provider profile reference'), { target: { value: 'VIP' } });
    fireEvent.click(screen.getByText('Save'));
    await waitFor(() => expect(api.createAccessProfile).toHaveBeenCalled());
  });
});

describe('Phase 14.1 Urgent attention UI', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.me).mockResolvedValue({
      ...globalAdmin,
      role: 'SECURITY',
      permissions: ['access.read', 'access.retry'],
    });
    vi.mocked(api.accessCredentials).mockImplementation(async (attention?: boolean) => {
      if (attention) {
        return [{
          id: 9,
          visitor_name: 'Rahul Sharma',
          location_name: 'Bangalore Office',
          location_id: 1,
          status: 'ACTIVE',
          visit_status: 'CHECKED_OUT',
          reason_code: 'CHECKED_OUT_ACCESS_ACTIVE',
          severity: 'URGENT',
          attention_title: 'Access still active after visitor checkout',
          valid_until: new Date().toISOString(),
          checked_out_at: new Date().toISOString(),
          visit_id: 10,
        }];
      }
      return [];
    });
    vi.mocked(api.badgePrintJobs).mockResolvedValue([]);
    vi.mocked(api.physicalIntegrationStatus).mockResolvedValue({ locations: [] });
  });

  it('shows URGENT checked-out active access', async () => {
    render(
      <BrowserRouter>
        <AccessOperationsPage />
      </BrowserRouter>,
    );
    await waitFor(() => expect(screen.getByText('Needs Attention')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Needs Attention'));
    await waitFor(() => {
      expect(screen.getByText('URGENT')).toBeInTheDocument();
      expect(screen.getByText(/Revocation is required/i)).toBeInTheDocument();
      expect(screen.getByText('Retry Revocation')).toBeInTheDocument();
    });
  });
});
