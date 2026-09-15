import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { VmsCopilotPage } from '../pages/vms-copilot/VmsCopilotPage';
import { filterNavByPermissions } from '../utils/permissions';

const mockCopilotResponse = {
  intent: 'OPERATIONAL_SUMMARY',
  provider: 'dev_mock',
  response: {
    answer: '2 item(s) need attention in Bangalore.',
    summary: '2 item(s) need attention.',
    insights: [],
    recommended_actions: [{ label: 'Review Pending Approvals', path: '/approvals' }],
    source_references: [{ label: 'Bangalore Onsite', path: '/onsite-now' }],
    limitations: ['AI-generated operational assistance. Verify important decisions in VMS.'],
    denied: false,
  },
};

vi.mock('../services/api', () => ({
  api: {
    copilotSuggestions: vi.fn(() => Promise.resolve({
      suggestions: ['Who is onsite right now?', 'Which approvals are waiting?'],
    })),
    copilotQuery: vi.fn(() => Promise.resolve(mockCopilotResponse)),
    aiInsights: vi.fn(() => Promise.resolve({ items: [] })),
    aiInsightsRefresh: vi.fn(() => Promise.resolve({ generated: 1 })),
    aiInsightDismiss: vi.fn(() => Promise.resolve({ id: 1, status: 'DISMISSED' })),
    locations: vi.fn(() => Promise.resolve([
      { id: 1, name: 'Bangalore', code: 'BLR', is_active: true, is_development_seed: true },
    ])),
  },
}));

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({
    user: {
      id: 1,
      email: 'siteadmin.blr@vms.local',
      role: 'SITE_ADMIN' as const,
      is_owner: false,
      is_active: true,
      permissions: ['ai.copilot.use', 'ai.operational.read', 'ai.insights.read', 'locations.read'],
      location_ids: [1],
      assigned_locations: [{ id: 1, name: 'Bangalore', code: 'BLR' }],
    },
    loading: false,
    error: null,
    unauthorized: false,
    reload: vi.fn(),
  }),
}));

describe('Phase 11 VMS Copilot', () => {
  it('renders copilot page', async () => {
    render(
      <BrowserRouter>
        <VmsCopilotPage />
      </BrowserRouter>,
    );
    expect(await screen.findByText('VMS Copilot')).toBeInTheDocument();
    expect(screen.getByText('Ask')).toBeInTheDocument();
    expect(screen.getByText('Insights')).toBeInTheDocument();
  });

  it('site admin nav includes copilot and dashboard, not management reports', () => {
    const perms = ['ai.copilot.use', 'visitor.read', 'onsite.read', 'locations.read'];
    const ids = filterNavByPermissions(perms).map((i) => i.id);
    expect(ids).toContain('vms-copilot');
    expect(ids).toContain('dashboard');
    expect(ids).not.toContain('reports');
  });
});
