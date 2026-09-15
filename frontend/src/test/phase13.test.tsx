import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { PrivacySecurityPage } from '../pages/administration/PrivacySecurityPage';

vi.mock('../services/api', () => ({
  api: {
    me: vi.fn().mockResolvedValue({
      id: 1,
      email: 'test@test.com',
      role: 'GLOBAL_ADMIN',
      permissions: ['privacy.retention.read', 'security.readiness.read', 'security.audit_integrity.read'],
      is_owner: true,
      is_active: true,
      location_ids: [],
      assigned_locations: [],
    }),
    retentionPolicies: vi.fn().mockResolvedValue([]),
    securityReadiness: vi.fn().mockResolvedValue({ ready: true, environment: 'development', checks: [] }),
    auditIntegrity: vi.fn().mockResolvedValue({ status: 'VALID', sealed_count: 0, legacy_count: 0 }),
    fileSecurityStatus: vi.fn().mockResolvedValue({ scanner_provider: 'dev_noop', encryption_enabled: false }),
  },
}));

import { safeReturnPath } from '../config/auth';

describe('Phase 13 safeReturnPath', () => {
  it('rejects open redirect targets', () => {
    expect(safeReturnPath('https://evil.example')).toBeNull();
    expect(safeReturnPath('//evil.example')).toBeNull();
    expect(safeReturnPath('javascript:alert(1)')).toBeNull();
    expect(safeReturnPath('/dashboard')).toBe('/dashboard');
  });
});

describe('Phase 13 PrivacySecurityPage', () => {
  it('renders page title', async () => {
    render(
      <BrowserRouter>
        <PrivacySecurityPage />
      </BrowserRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('Privacy & Security')).toBeInTheDocument();
    });
  });
});
