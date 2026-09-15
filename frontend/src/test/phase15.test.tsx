import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { OperationsReadinessPage } from '../pages/administration/OperationsReadinessPage';

vi.mock('../services/api', () => ({
  api: {
    me: vi.fn(),
    operationsReadiness: vi.fn().mockResolvedValue({
      evaluated_at: '2026-08-26T00:00:00Z',
      runtime_instance_id: 'inst-abc12345',
      production_readiness: { environment: 'development', ready: true },
      database: {
        dialect: 'SQLite',
        environment_label: 'DEVELOPMENT',
        connected: true,
        schema_revision: null,
        schema_revision_display: null,
        schema_current: false,
        postgres_validation: 'DEVELOPMENT',
        pool_size: null,
        pool_in_use: null,
        pool_state: 'HEALTHY',
        pool_healthy: true,
      },
      schedulers: [
        {
          scheduler: 'notification-dispatch',
          lease_state: 'STANDBY',
          lease_expires_at: null,
          last_success_at: null,
          last_error_code: null,
          owner_masked: null,
        },
      ],
      queues: {
        notifications_pending: 0,
        notifications_failed: 0,
        notifications_backlog_level: 'HEALTHY',
        access_provisioning_pending: 0,
        access_revocations_pending: 0,
        badge_print_pending: 0,
        badge_print_failed: 0,
        physical_queue_backlog_level: 'HEALTHY',
        retention_last_run_at: null,
      },
      integrations: [{ key: 'email', label: 'Email Provider', status: 'DEVELOPMENT_ONLY', detail: 'dev_outbox' }],
      audit_integrity: { status: 'VALID', verified_at: '2026-08-26T00:00:00Z', sealed_count: 1 },
      security: { auth_mode: 'dev', rate_limit_backend: 'memory', log_format: 'text' },
    }),
  },
}));

import { api } from '../services/api';

describe('Phase 15 OperationsReadinessPage', () => {
  beforeEach(() => {
    vi.mocked(api.me).mockResolvedValue({
      id: 1,
      email: 'global@vms.local',
      display_name: 'Global Admin',
      role: 'GLOBAL_ADMIN',
      is_owner: false,
      is_active: true,
      permissions: ['operations.readiness.read'],
      location_ids: [],
      assigned_locations: [],
    });
  });

  it('renders for Global Admin with SQLite development label', async () => {
    render(
      <BrowserRouter>
        <OperationsReadinessPage />
      </BrowserRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('Operations & Deployment Readiness')).toBeInTheDocument();
      expect(screen.getByText('SQLite')).toBeInTheDocument();
      expect(screen.getAllByText('DEVELOPMENT').length).toBeGreaterThan(0);
      expect(screen.getByText('notification-dispatch')).toBeInTheDocument();
    });
    expect(screen.queryByText('GRAPH_CLIENT_SECRET')).toBeNull();
  });

  it('shows read-only hint for Head Admin', async () => {
    vi.mocked(api.me).mockResolvedValue({
      id: 2,
      email: 'head@vms.local',
      display_name: 'Head Admin',
      role: 'HEAD_ADMIN',
      is_owner: false,
      is_active: true,
      permissions: ['operations.readiness.read'],
      location_ids: [],
      assigned_locations: [],
    });
    render(
      <BrowserRouter>
        <OperationsReadinessPage />
      </BrowserRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/Read-only view/)).toBeInTheDocument();
    });
  });
});

describe('Phase 15 permission expectations', () => {
  it('Site Admin and Security lack operations.readiness.read in nav filter', async () => {
    const { filterNavByPermissions } = await import('../utils/permissions');
    expect(filterNavByPermissions(['operations.readiness.read']).some((i) => i.id === 'operations-readiness')).toBe(true);
    expect(filterNavByPermissions(['visitor.read']).some((i) => i.id === 'operations-readiness')).toBe(false);
  });
});
