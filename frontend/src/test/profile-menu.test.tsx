import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ProfileMenu } from '../components/admin/ProfileMenu';
import { PreferencesProvider } from '../contexts/PreferencesContext';
import { ProfilePage } from '../pages/profile/ProfilePage';
import { PreferencesPage } from '../pages/profile/PreferencesPage';
import { getProfileAdminLinks } from '../utils/profileMenuConfig';
import { formatRoleLabel, getInitials } from '../utils/userDisplay';
import {
  loadUserPreferences,
  saveUserPreferences,
  resolveThemePreference,
  getDefaultLandingPath,
  isLandingPageAllowed,
} from '../utils/userPreferences';
import type { UserProfile } from '../types';

vi.mock('../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}));

import { useAuth } from '../hooks/useAuth';

const globalAdmin: UserProfile = {
  id: 1,
  email: 'sheru.bohra@lazypay.in',
  display_name: 'Sheru Bohra',
  role: 'GLOBAL_ADMIN',
  is_owner: true,
  is_active: true,
  permissions: [
    'analytics.dashboard.view',
    'visitor.read',
    'reports.view',
    'admins.read',
    'privacy.retention.read',
    'access.config.read',
    'operations.readiness.read',
    'locations.read',
    'arrival.read',
    'onsite.read',
    'approval.read',
  ],
  location_ids: [],
  assigned_locations: [],
  auth_provider: 'dev',
};

const siteAdmin: UserProfile = {
  id: 2,
  email: 'siteadmin.blr@vms.local',
  display_name: 'Site Admin BLR',
  role: 'SITE_ADMIN',
  is_owner: false,
  is_active: true,
  permissions: ['visitor.read', 'arrival.read', 'onsite.read', 'approval.read'],
  location_ids: [1],
  assigned_locations: [{ id: 1, name: 'Bangalore Office', code: 'BLR', city: 'Bangalore' }],
};

const securityUser: UserProfile = {
  id: 3,
  email: 'security.blr@vms.local',
  display_name: 'Security BLR',
  role: 'SECURITY',
  is_owner: false,
  is_active: true,
  permissions: ['visitor_qr.verify', 'arrival.read', 'onsite.read', 'security_screening.read'],
  location_ids: [1],
  assigned_locations: [{ id: 1, name: 'Bangalore Office', code: 'BLR', city: 'Bangalore' }],
};

function renderWithProviders(user: UserProfile) {
  return render(
    <BrowserRouter>
      <PreferencesProvider user={user}>
        <ProfileMenu user={user} />
      </PreferencesProvider>
    </BrowserRouter>,
  );
}

describe('profile menu', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders current user in trigger', () => {
    renderWithProviders(globalAdmin);
    expect(screen.getByText('Sheru Bohra')).toBeInTheDocument();
    expect(screen.getByText('Global Admin')).toBeInTheDocument();
  });

  it('opens menu on click and shows owner badge', () => {
    renderWithProviders(globalAdmin);
    fireEvent.click(screen.getByLabelText('Account menu'));
    expect(screen.getByText('sheru.bohra@lazypay.in')).toBeInTheDocument();
    expect(screen.getByText('Owner')).toBeInTheDocument();
    expect(screen.getByText('Users & Access')).toBeInTheDocument();
  });

  it('closes on Escape', () => {
    renderWithProviders(globalAdmin);
    fireEvent.click(screen.getByLabelText('Account menu'));
    expect(screen.getByText('Sign Out')).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByText('Sign Out')).not.toBeInTheDocument();
  });

  it('shows compact menu for Site Admin without admin links', () => {
    renderWithProviders(siteAdmin);
    fireEvent.click(screen.getByLabelText('Account menu'));
    expect(screen.getByText('My Profile')).toBeInTheDocument();
    expect(screen.queryByText('Users & Access')).not.toBeInTheDocument();
    expect(screen.queryByText('Privacy & Security')).not.toBeInTheDocument();
  });

  it('shows compact menu for Security without admin links', () => {
    renderWithProviders(securityUser);
    fireEvent.click(screen.getByLabelText('Account menu'));
    expect(screen.getByText('My Access')).toBeInTheDocument();
    expect(screen.queryByText('Users & Access')).not.toBeInTheDocument();
    expect(screen.queryByText('Operations Readiness')).not.toBeInTheDocument();
  });

  it('derives admin links from permissions', () => {
    const links = getProfileAdminLinks(globalAdmin.permissions);
    expect(links.map((l) => l.label)).toContain('Users & Access');
    expect(getProfileAdminLinks(siteAdmin.permissions)).toHaveLength(0);
  });
});

describe('user display helpers', () => {
  it('formats role labels', () => {
    expect(formatRoleLabel('GLOBAL_ADMIN')).toBe('Global Admin');
    expect(formatRoleLabel('SITE_ADMIN')).toBe('Site Admin');
  });

  it('generates two-letter initials', () => {
    expect(getInitials('Sheru Bohra', 'sheru@payu.in')).toBe('SB');
  });
});

describe('user preferences', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('persists theme per user', () => {
    saveUserPreferences(1, { ...loadUserPreferences(1), theme: 'dark' });
    expect(loadUserPreferences(1).theme).toBe('dark');
    expect(loadUserPreferences(2).theme).toBe('light');
  });

  it('resolves system theme', () => {
    expect(resolveThemePreference('light')).toBe('light');
    expect(resolveThemePreference('dark')).toBe('dark');
  });

  it('validates landing pages by permission', () => {
    expect(isLandingPageAllowed('/reports', globalAdmin.permissions)).toBe(true);
    expect(isLandingPageAllowed('/reports', securityUser.permissions)).toBe(false);
  });

  it('uses saved landing page when permitted', () => {
    saveUserPreferences(1, { ...loadUserPreferences(1), defaultLandingPage: '/visitors' });
    expect(getDefaultLandingPath(1, globalAdmin.permissions, 'GLOBAL_ADMIN')).toBe('/visitors');
  });
});

describe('profile and preferences pages', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.mocked(useAuth).mockReturnValue({
      user: globalAdmin,
      loading: false,
      error: null,
      unauthorized: false,
      reload: vi.fn(),
    });
  });

  it('profile page shows read-only identity', () => {
    render(
      <BrowserRouter>
        <PreferencesProvider user={globalAdmin}>
          <ProfilePage />
        </PreferencesProvider>
      </BrowserRouter>,
    );
    expect(screen.getByText('Sheru Bohra')).toBeInTheDocument();
    expect(screen.getByText('sheru.bohra@lazypay.in')).toBeInTheDocument();
  });

  it('preferences page renders theme options', () => {
    render(
      <BrowserRouter>
        <PreferencesProvider user={globalAdmin}>
          <PreferencesPage />
        </PreferencesProvider>
      </BrowserRouter>,
    );
    expect(screen.getByText('Preferences')).toBeInTheDocument();
    expect(screen.getByText('Dark')).toBeInTheDocument();
  });
});
