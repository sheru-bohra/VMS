import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { VendorsContractorsPage } from '../pages/vendors/VendorsContractorsPage';
import { api } from '../services/api';

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({
    user: {
      permissions: ['vendor_company.read', 'vendor_company.manage', 'compliance.read'],
      assigned_locations: [{ id: 1, name: 'Bangalore Office', code: 'BLR' }],
    },
    loading: false,
  }),
}));

vi.mock('../services/api', () => ({
  api: {
    vendorCompanies: vi.fn(),
    contractorVisits: vi.fn(),
    complianceReviews: vi.fn(),
  },
}));

describe('Phase 8 vendors page', () => {
  beforeEach(() => {
    vi.mocked(api.vendorCompanies).mockResolvedValue({
      items: [{
        id: 1,
        name: 'ABC Services',
        is_active: true,
        locations: [{ id: 1, name: 'Bangalore Office', code: 'BLR' }],
      }],
      total: 1,
      limit: 50,
      offset: 0,
    });
  });

  it('Vendors & Contractors page renders', async () => {
    render(<BrowserRouter><VendorsContractorsPage /></BrowserRouter>);
    await waitFor(() => {
      expect(screen.getByText('Vendors & Contractors')).toBeInTheDocument();
      expect(screen.getByText('ABC Services')).toBeInTheDocument();
    });
  });
});
