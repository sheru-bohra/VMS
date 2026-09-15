import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { VmsLoginPage } from '../pages/login/VmsLoginPage';
import { ProfilePage } from '../pages/profile/ProfilePage';

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock('../services/api', () => ({
  api: {
    login: vi.fn(),
    me: vi.fn(),
    changePassword: vi.fn(),
  },
  ApiClientError: class ApiClientError extends Error {
    status: number;
    constructor(message: string, status = 400) {
      super(message);
      this.status = status;
    }
  },
}));

vi.mock('../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}));

import { api } from '../services/api';
import { useAuth } from '../hooks/useAuth';

describe('VmsLoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.login).mockResolvedValue({
      access_token: 'token',
      token_type: 'Bearer',
      expires_in: 3600,
      force_password_change: false,
    });
    vi.mocked(api.me).mockResolvedValue({
      id: 1,
      email: 'admin@lazypay.in',
      display_name: 'Admin',
      role: 'GLOBAL_ADMIN',
      is_owner: true,
      is_active: true,
      auth_provider: 'vms_native',
      permissions: [],
      location_ids: [],
      assigned_locations: [],
      force_password_change: false,
    });
  });

  it('renders polished login branding and fields', () => {
    render(
      <MemoryRouter>
        <VmsLoginPage />
      </MemoryRouter>,
    );
    expect(screen.getByAltText('PayU')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument();
    expect(screen.getByText('Sign in to your Visitor Management account.')).toBeInTheDocument();
    expect(screen.getByLabelText('Corporate Email')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('name@company.com')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Enter your password')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign In' })).toBeInTheDocument();
    expect(screen.getByText('Authorized staff access only')).toBeInTheDocument();
  });

  it('toggles password visibility', () => {
    render(
      <MemoryRouter>
        <VmsLoginPage />
      </MemoryRouter>,
    );
    const password = screen.getByLabelText('Password') as HTMLInputElement;
    expect(password.type).toBe('password');
    fireEvent.click(screen.getByRole('button', { name: 'Show password' }));
    expect(password.type).toBe('text');
    fireEvent.click(screen.getByRole('button', { name: 'Hide password' }));
    expect(password.type).toBe('password');
  });

  it('submits login and navigates on success', async () => {
    render(
      <MemoryRouter>
        <VmsLoginPage />
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByLabelText('Corporate Email'), { target: { value: 'admin@lazypay.in' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'secret' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign In' }));
    await waitFor(() => {
      expect(api.login).toHaveBeenCalledWith('admin@lazypay.in', 'secret');
      expect(mockNavigate).toHaveBeenCalled();
    });
  });

  it('shows generic error on invalid login', async () => {
    const { ApiClientError } = await import('../services/api');
    vi.mocked(api.login).mockRejectedValue(new ApiClientError('Invalid email or password.', 401));
    render(
      <MemoryRouter>
        <VmsLoginPage />
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByLabelText('Corporate Email'), { target: { value: 'admin@lazypay.in' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'bad' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign In' }));
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Unable to sign in');
      expect(screen.getByRole('alert')).toHaveTextContent('Please check your email and password and try again.');
    });
  });

  it('shows loading state while signing in', async () => {
    vi.mocked(api.login).mockImplementation(
      () => new Promise((resolve) => {
        setTimeout(
          () =>
            resolve({
              access_token: 'token',
              token_type: 'Bearer',
              expires_in: 3600,
              force_password_change: false,
            }),
          50,
        );
      }),
    );
    render(
      <MemoryRouter>
        <VmsLoginPage />
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByLabelText('Corporate Email'), { target: { value: 'admin@lazypay.in' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'secret' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign In' }));
    expect(screen.getByRole('button', { name: 'Signing in…' })).toBeDisabled();
    await waitFor(() => expect(mockNavigate).toHaveBeenCalled());
  });
});

describe('ProfilePage password management', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows change password tab for Global Admin with vms_native auth', async () => {
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: 1,
        email: 'admin@lazypay.in',
        display_name: 'Admin',
        role: 'GLOBAL_ADMIN',
        is_owner: true,
        is_active: true,
        auth_provider: 'vms_native',
        permissions: ['locations.read'],
        location_ids: [],
        assigned_locations: [],
      },
      loading: false,
      error: null,
      unauthorized: false,
      reload: vi.fn(),
    });
    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: 'Change Password' })).toBeInTheDocument();
  });

  it('does not show change password tab for site admin', async () => {
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: 2,
        email: 'site@lazypay.in',
        display_name: 'Site Admin',
        role: 'SITE_ADMIN',
        is_owner: false,
        is_active: true,
        auth_provider: 'vms_native',
        permissions: [],
        location_ids: [1],
        assigned_locations: [{ id: 1, name: 'BLR', code: 'BLR' }],
      },
      loading: false,
      error: null,
      unauthorized: false,
      reload: vi.fn(),
    });
    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    );
    expect(screen.queryByRole('button', { name: 'Change Password' })).not.toBeInTheDocument();
  });
});
