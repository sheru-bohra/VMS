import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AccessOperationsPage } from '../pages/access-operations/AccessOperationsPage';
import { AccessBadgesAdminPage } from '../pages/administration/AccessBadgesAdminPage';

const securityUser = {
  id: 2,
  email: 'security.blr@vms.local',
  role: 'SECURITY',
  permissions: ['access.read', 'access.operate', 'access.retry', 'access.revoke', 'badge.printer.read', 'badge.printer.operate'],
  is_owner: false,
  is_active: true,
  location_ids: [1],
  assigned_locations: [{ id: 1, name: 'Bangalore Office', code: 'BLR' }],
};

const globalAdminUser = {
  id: 1,
  email: 'admin@test.com',
  role: 'GLOBAL_ADMIN',
  permissions: ['access.config.read', 'access.config.manage', 'badge.printer.config.manage'],
  is_owner: true,
  is_active: true,
  location_ids: [],
  assigned_locations: [],
};

vi.mock('../services/api', () => ({
  api: {
    me: vi.fn(),
    locations: vi.fn().mockResolvedValue([{ id: 1, name: 'Bangalore Office', code: 'BLR', is_active: true }]),
    accessCredentials: vi.fn(),
    badgePrintJobs: vi.fn(),
    physicalIntegrationStatus: vi.fn(),
    retryAccessCredential: vi.fn().mockResolvedValue({}),
    revokeAccessCredential: vi.fn().mockResolvedValue({}),
    retryBadgePrintJob: vi.fn().mockResolvedValue({}),
    accessProfiles: vi.fn(),
    accessProfileMappings: vi.fn(),
    badgePrinters: vi.fn(),
    accessLocationConfigs: vi.fn(),
    visitorTypes: vi.fn().mockResolvedValue([]),
  },
}));

import { api } from '../services/api';

describe('Phase 14 Access Operations', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.me).mockResolvedValue(securityUser);
    vi.mocked(api.accessCredentials).mockResolvedValue([
      {
        id: 1,
        visitor_name: 'Rahul Sharma',
        location_name: 'Bangalore Office',
        access_profile_name: 'Standard Visitor',
        status: 'ACTIVE',
        valid_until: new Date().toISOString(),
        last_error_code: null,
        visit_id: 10,
      },
    ]);
    vi.mocked(api.badgePrintJobs).mockResolvedValue([
      {
        id: 5,
        visitor_name: 'Rahul Sharma',
        badge_number: 'B-001',
        location_name: 'Bangalore Office',
        printer_name: 'Reception Printer',
        status: 'FAILED',
        visit_id: 10,
      },
    ]);
    vi.mocked(api.physicalIntegrationStatus).mockResolvedValue({
      access_control_enabled: true,
      access_provider: 'dev_mock',
      badge_printer_enabled: true,
      badge_printer_provider: 'dev_mock',
      locations: [{ location_id: 1, access_health: 'HEALTHY' }],
    });
  });

  it('renders access operations page with tabs', async () => {
    render(
      <BrowserRouter>
        <AccessOperationsPage />
      </BrowserRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('Access Operations')).toBeInTheDocument();
      expect(screen.getByText('Active Access')).toBeInTheDocument();
      expect(screen.getByText('Needs Attention')).toBeInTheDocument();
      expect(screen.getByText('Badge Print Jobs')).toBeInTheDocument();
    });
  });

  it('shows active credentials and revoke confirmation', async () => {
    render(
      <BrowserRouter>
        <AccessOperationsPage />
      </BrowserRouter>,
    );
    await waitFor(() => expect(screen.getByText('Rahul Sharma')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Revoke'));
    expect(screen.getByText(/does not check the visitor out/i)).toBeInTheDocument();
  });

  it('retry and browser badge fallback on print jobs', async () => {
    render(
      <BrowserRouter>
        <AccessOperationsPage />
      </BrowserRouter>,
    );
    await waitFor(() => expect(screen.getByText('Badge Print Jobs')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Badge Print Jobs'));
    await waitFor(() => {
      expect(screen.getByText('Browser Badge')).toBeInTheDocument();
      expect(screen.getByText('Retry')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('Retry'));
    await waitFor(() => expect(api.retryBadgePrintJob).toHaveBeenCalledWith(5));
  });
});

describe('Phase 14 Access & Badge Administration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.me).mockResolvedValue(globalAdminUser);
    vi.mocked(api.accessProfiles).mockResolvedValue([
      { id: 1, name: 'Standard Visitor', location_id: 1, provider_external_profile_ref: 'profile-1', is_active: true },
    ]);
    vi.mocked(api.accessProfileMappings).mockResolvedValue([
      { id: 1, visitor_type_name: 'Business Visitor', access_profile_name: 'Standard Visitor', location_id: 1 },
    ]);
    vi.mocked(api.badgePrinters).mockResolvedValue([
      { id: 1, name: 'Reception Printer', location_id: 1, is_default: true, is_active: true },
    ]);
    vi.mocked(api.accessLocationConfigs).mockResolvedValue([
      {
        id: 1,
        location_name: 'Bangalore Office',
        access_control_enabled: true,
        provider_key: 'dev_mock',
        credential_grace_minutes: 30,
        max_credential_duration_minutes: 480,
      },
    ]);
  });

  it('renders administration tabs', async () => {
    render(
      <BrowserRouter>
        <AccessBadgesAdminPage />
      </BrowserRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('Access & Badge Administration')).toBeInTheDocument();
      expect(screen.getByText('Access Profiles')).toBeInTheDocument();
      expect(screen.getByText('Standard Visitor')).toBeInTheDocument();
    });
  });

  it('security user sees read-only configuration', async () => {
    vi.mocked(api.me).mockResolvedValue({
      ...securityUser,
      permissions: ['access.config.read', 'badge.printer.read'],
    });
    render(
      <BrowserRouter>
        <AccessBadgesAdminPage />
      </BrowserRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('Read-only configuration view.')).toBeInTheDocument();
    });
  });
});
