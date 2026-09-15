import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AdminRoutes } from '../app/App';
import { App } from '../app/App';
import { VmsLoginPage } from '../pages/login/VmsLoginPage';
import {
  getUnauthenticatedLoginRedirect,
  shouldHandleApiUnauthorized,
} from '../auth/authRedirect';
import { safeReturnPath } from '../config/auth';

const reload = vi.fn();

vi.mock('../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}));

vi.mock('../services/api', () => ({
  api: {
    login: vi.fn(),
    me: vi.fn(),
  },
  ApiClientError: class ApiClientError extends Error {
    status: number;
    constructor(message: string, status = 400) {
      super(message);
      this.status = status;
    }
  },
}));

import { useAuth } from '../hooks/useAuth';

describe('auth redirect helpers', () => {
  it('builds login path with safe returnTo', () => {
    expect(getUnauthenticatedLoginRedirect('/dashboard')).toBe('/login?returnTo=%2Fdashboard');
    expect(getUnauthenticatedLoginRedirect('/visitors', '?tab=active')).toBe(
      '/login?returnTo=%2Fvisitors%3Ftab%3Dactive',
    );
  });

  it('rejects external returnTo URLs', () => {
    expect(safeReturnPath('https://evil.example')).toBeNull();
    expect(getUnauthenticatedLoginRedirect('/', '?returnTo=https://evil.example')).toBe('/login');
  });

  it('does not redirect 403 or login/me health calls through API unauthorized handler', () => {
    expect(shouldHandleApiUnauthorized('/api/auth/login')).toBe(false);
    expect(shouldHandleApiUnauthorized('/api/me')).toBe(false);
    expect(shouldHandleApiUnauthorized('/api/visitors')).toBe(true);
  });
});

describe('AdminRoutes authentication guard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('redirects unauthenticated /dashboard to login with returnTo', async () => {
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      loading: false,
      error: null,
      unauthorized: true,
      reload,
    });

    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route path="/login" element={<VmsLoginPage />} />
          <Route path="/*" element={<AdminRoutes />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByLabelText('Corporate Email')).toBeInTheDocument();
      expect(screen.getByLabelText('Password')).toBeInTheDocument();
    });
  });

  it('shows loading state while session initializes', () => {
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      loading: true,
      error: null,
      unauthorized: false,
      reload,
    });

    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route path="/*" element={<AdminRoutes />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText('Loading admin session…')).toBeInTheDocument();
  });

  it('does not redirect while loading', () => {
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      loading: true,
      error: null,
      unauthorized: false,
      reload,
    });

    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route path="/login" element={<VmsLoginPage />} />
          <Route path="/*" element={<AdminRoutes />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.queryByLabelText('Corporate Email')).not.toBeInTheDocument();
  });

  it('shows session error instead of login redirect', () => {
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      loading: false,
      error: 'Network error',
      unauthorized: false,
      reload,
    });

    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route path="/*" element={<AdminRoutes />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText('Unable to load session')).toBeInTheDocument();
    expect(screen.queryByLabelText('Corporate Email')).not.toBeInTheDocument();
  });

  it('redirects unauthenticated /administration to login', async () => {
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      loading: false,
      error: null,
      unauthorized: true,
      reload,
    });

    render(
      <MemoryRouter initialEntries={['/administration']}>
        <Routes>
          <Route path="/login" element={<VmsLoginPage />} />
          <Route path="/*" element={<AdminRoutes />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Sign In' })).toBeInTheDocument();
    });
  });
});

describe('App public login route', () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      loading: false,
      error: null,
      unauthorized: true,
      reload,
    });
  });

  afterEach(() => {
    window.history.pushState({}, '', '/');
  });

  it('renders login page at /login without authentication', async () => {
    window.history.pushState({}, '', '/login');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByLabelText('Corporate Email')).toBeInTheDocument();
      expect(screen.queryByText('Authentication required')).not.toBeInTheDocument();
    });
  });
});
