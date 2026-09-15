import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import {
  COMPLETED_STAFF_ROUTES,
  PLACEHOLDER_BANNED_TEXT,
} from '../app/routeRegistry';
import { VisitorsPage } from '../pages/visitors/VisitorsPage';
import { AdministrationPage } from '../pages/administration/AdministrationPage';

const mockGlobalAdmin = {
  id: 1,
  email: 'admin@test.com',
  display_name: 'Global Admin',
  role: 'GLOBAL_ADMIN' as const,
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
  ],
  location_ids: [1],
};

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({ user: mockGlobalAdmin, loading: false, error: null, unauthorized: false, reload: vi.fn() }),
}));

vi.mock('../hooks/useOperationalLocations', () => ({
  useOperationalLocations: () => [{ id: 1, name: 'Bangalore', code: 'BLR' }],
}));

vi.mock('../services/api', () => ({
  api: {
    visitorVisits: vi.fn().mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 }),
    analyticsDashboard: vi.fn().mockResolvedValue({
      period: 'today',
      totals: { visitors: 0, check_ins: 0, onsite: 0, rejected: 0 },
      by_location: [],
      by_visitor_type: [],
      by_status: [],
    }),
    reportVisits: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 50 }),
    vendorCompanies: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    complianceReviews: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    contractorVisits: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    expectedToday: vi.fn().mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 }),
    onsiteVisitors: vi.fn().mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0, onsite_count: 0 }),
    invitations: vi.fn().mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 }),
    selfRegistrations: vi.fn().mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 }),
    approvals: vi.fn().mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 }),
    watchlistEntries: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    securityReviews: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    emergencyEvents: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    locationsAdmin: vi.fn().mockResolvedValue([]),
    accessCredentials: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    aiCopilotQuery: vi.fn().mockResolvedValue({ answer: 'ok', citations: [] }),
    administrationUsers: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    retentionPolicies: vi.fn().mockResolvedValue([]),
    operationsReadiness: vi.fn().mockResolvedValue({ checks: [] }),
  },
  ApiClientError: class extends Error {},
}));

describe('route wiring — no placeholder shells', () => {
  it('App.tsx does not reference PlaceholderPage', () => {
    const appPath = resolve(__dirname, '../app/App.tsx');
    const src = readFileSync(appPath, 'utf8');
    expect(src).not.toContain('PlaceholderPage');
    expect(src).not.toContain('ComingSoon');
  });

  it('VisitorsPage renders real module UI', async () => {
    render(
      <BrowserRouter>
        <VisitorsPage />
      </BrowserRouter>,
    );
    expect(screen.getByText('Visitors')).toBeInTheDocument();
    expect(screen.getByText(/Visitor records and visit history/)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText('No visitors found')).toBeInTheDocument();
    });
    for (const banned of PLACEHOLDER_BANNED_TEXT) {
      expect(screen.queryByText(new RegExp(banned, 'i'))).toBeNull();
    }
  });

  it('AdministrationPage renders administration hub', () => {
    render(
      <BrowserRouter>
        <AdministrationPage />
      </BrowserRouter>,
    );
    expect(screen.getByText('Administration')).toBeInTheDocument();
    expect(screen.getByText('Users & Access')).toBeInTheDocument();
    for (const banned of PLACEHOLDER_BANNED_TEXT) {
      expect(screen.queryByText(new RegExp(banned, 'i'))).toBeNull();
    }
  });

  it('completed staff route registry has no placeholder-only routes', () => {
    expect(COMPLETED_STAFF_ROUTES.length).toBeGreaterThanOrEqual(15);
    const paths = COMPLETED_STAFF_ROUTES.map((r) => r.path);
    expect(paths).toContain('/visitors');
    expect(paths).toContain('/dashboard');
    expect(paths).toContain('/reports');
    expect(paths).toContain('/vendors-contractors');
    expect(paths).toContain('/administration');
  });
});
