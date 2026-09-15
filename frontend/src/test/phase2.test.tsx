import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter, MemoryRouter, Route, Routes } from 'react-router-dom';
import { VisitorRegistrationPage } from '../pages/visit/VisitorRegistrationPage';
import { RegistrationSuccessPage } from '../pages/visit/RegistrationSuccessPage';
import { SelfRegistrationsPage } from '../pages/self-registrations/SelfRegistrationsPage';
import { api } from '../services/api';

vi.mock('../services/api', () => ({
  api: {
    publicSite: vi.fn(),
    publicVisitorTypes: vi.fn(),
    publicHosts: vi.fn(),
    publicPolicy: vi.fn(),
    submitRegistration: vi.fn(),
    selfRegistrations: vi.fn(),
    selfRegistrationDetail: vi.fn(),
  },
  ApiClientError: class extends Error {
    status = 400;
    code = 'error';
  },
}));

describe('VisitorRegistrationPage', () => {
  beforeEach(() => {
    vi.mocked(api.publicSite).mockResolvedValue({ name: 'Development Main Office', registration_enabled: true });
    vi.mocked(api.publicVisitorTypes).mockResolvedValue([{ code: 'BUSINESS', name: 'Business Visitor' }]);
    vi.mocked(api.publicHosts).mockResolvedValue([{ id: 1, name: 'Amit Kumar', department: 'Engineering' }]);
  });

  it('renders site name from token', async () => {
    render(
      <MemoryRouter initialEntries={['/visit/register/test-token-abc']}>
        <Routes>
          <Route path="/visit/register/:siteToken" element={<VisitorRegistrationPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('Development Main Office')).toBeInTheDocument();
    });
  });

  it('renders invalid token state', async () => {
    vi.mocked(api.publicSite).mockRejectedValue(new Error('not found'));
    render(
      <MemoryRouter initialEntries={['/visit/register/bad-token']}>
        <Routes>
          <Route path="/visit/register/:siteToken" element={<VisitorRegistrationPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('Visitor Registration Unavailable')).toBeInTheDocument();
    });
  });

  it('validates required fields', async () => {
    render(
      <MemoryRouter initialEntries={['/visit/register/test-token']}>
        <Routes>
          <Route path="/visit/register/:siteToken" element={<VisitorRegistrationPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => screen.getByText('Development Main Office'));
    fireEvent.click(screen.getByRole('button', { name: /submit registration/i }));
    await waitFor(() => {
      expect(screen.getByText('Please select a visitor type.')).toBeInTheDocument();
    });
  });
});

describe('RegistrationSuccessPage', () => {
  it('renders success state with reference', () => {
    render(
      <MemoryRouter
        initialEntries={[
          {
            pathname: '/visit/register/token/success',
            state: {
              reference: 'VMS-260826-0042',
              visitorName: 'Test Visitor',
              siteName: 'Development Main Office',
              status: 'PENDING_APPROVAL',
            },
          },
        ]}
      >
        <Routes>
          <Route path="/visit/register/:siteToken/success" element={<RegistrationSuccessPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('Registration received')).toBeInTheDocument();
    expect(screen.getByText('VMS-260826-0042')).toBeInTheDocument();
    expect(screen.getByText(/Awaiting Approval|PENDING APPROVAL/i)).toBeInTheDocument();
  });
});

describe('SelfRegistrationsPage', () => {
  it('renders self registrations table', async () => {
    vi.mocked(api.selfRegistrations).mockResolvedValue({
      items: [
        {
          id: 1,
          registration_reference: 'VMS-260826-0001',
          status: 'PENDING_APPROVAL',
          visitor_name: 'Jane Doe',
          visitor_mobile: '+1234567890',
          visitor_email: 'jane@test.com',
          company: 'Acme',
          visitor_type: 'Business Visitor',
          host_name: 'Amit Kumar',
          site_name: 'Development Main Office',
          site_id: 1,
          purpose: 'Meeting',
          expected_duration_minutes: 60,
          policy_accepted: true,
          submitted_at: new Date().toISOString(),
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });

    render(
      <BrowserRouter>
        <SelfRegistrationsPage />
      </BrowserRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Self Registrations')).toBeInTheDocument();
      expect(screen.getByText('Jane Doe')).toBeInTheDocument();
      expect(screen.getByText('VMS-260826-0001')).toBeInTheDocument();
    });
  });
});
