import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { WatchlistPage } from '../pages/watchlist/WatchlistPage';
import { SecurityReviewPage } from '../pages/security-review/SecurityReviewPage';
import { api } from '../services/api';

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({
    user: {
      permissions: [
        'watchlist.read',
        'watchlist.create',
        'watchlist.create_location',
        'watchlist.deactivate',
        'security_screening.read',
        'security_screening.resolve',
      ],
      assigned_locations: [{ id: 1, name: 'Bangalore Office', code: 'BLR', city: 'Bangalore' }],
    },
    loading: false,
  }),
}));

vi.mock('../services/api', () => ({
  api: {
    watchlist: vi.fn(),
    watchlistDetail: vi.fn(),
    createWatchlistEntry: vi.fn(),
    deactivateWatchlistEntry: vi.fn(),
    securityReviews: vi.fn(),
    securityReviewDetail: vi.fn(),
    clearSecurityReview: vi.fn(),
    blockSecurityReview: vi.fn(),
  },
  ApiClientError: class extends Error { status = 403; code = 'forbidden'; },
}));

describe('Phase 7 pages', () => {
  beforeEach(() => {
    vi.mocked(api.watchlist).mockResolvedValue({
      items: [{
        id: 1,
        scope_type: 'GLOBAL',
        location_id: null,
        location_name: null,
        full_name: 'Rahul Sharma',
        mobile: '+919876543210',
        email: null,
        company: 'ABC Ltd',
        reason_code: 'ACCESS_RESTRICTED',
        reason_text: null,
        action_level: 'BLOCK',
        status: 'ACTIVE',
        valid_from: new Date().toISOString(),
        valid_until: null,
        created_at: new Date().toISOString(),
        deactivated_at: null,
      }],
      total: 1,
      limit: 50,
      offset: 0,
    });
    vi.mocked(api.securityReviews).mockResolvedValue({
      items: [{
        visit_id: 10,
        registration_reference: 'VMS-260826-0001',
        status: 'PENDING_APPROVAL',
        source: 'self_registration',
        security_status: 'REVIEW',
        visitor_name: 'Rahul Sharma',
        visitor_mobile: '+919876543210',
        visitor_email: 'test@test.com',
        company: 'ABC Ltd',
        visitor_type: 'Business',
        host_name: 'Amit',
        site_name: 'Bangalore Office',
        site_id: 1,
        purpose: 'Meeting',
        screening_outcome: 'REVIEW',
        match_confidence: 'STRONG',
        reason_summary: 'Watchlist match detected',
        signals: ['Mobile exact match'],
        screening_id: 1,
        resolved: false,
        resolution: null,
        screened_at: new Date().toISOString(),
      }],
      total: 1,
      review_count: 1,
      blocked_count: 0,
      limit: 50,
      offset: 0,
    });
  });

  it('Watchlist page renders', async () => {
    render(<BrowserRouter><WatchlistPage /></BrowserRouter>);
    await waitFor(() => {
      expect(screen.getByText('Watchlist')).toBeInTheDocument();
      expect(screen.getByText('Rahul Sharma')).toBeInTheDocument();
    });
    expect(screen.getByText('Add Entry')).toBeInTheDocument();
  });

  it('Security Review page renders', async () => {
    render(<BrowserRouter><SecurityReviewPage /></BrowserRouter>);
    await waitFor(() => {
      expect(screen.getByText('Security Review')).toBeInTheDocument();
      expect(screen.getByText('Rahul Sharma')).toBeInTheDocument();
    });
    expect(screen.getByText(/Needs Review/)).toBeInTheDocument();
  });
});
