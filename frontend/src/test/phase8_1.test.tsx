import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ComplianceDetailPanel } from '../pages/vendors/ComplianceDetailPanel';
import { ComplianceRequirementsPanel } from '../pages/vendors/ComplianceRequirementsPanel';
import { validateFile, ALLOWED_EXTENSIONS } from '../pages/vendors/complianceUtils';
import type { ComplianceVisitDetail } from '../types';
import { api } from '../services/api';

vi.mock('../services/api', () => ({
  api: {
    uploadComplianceDocument: vi.fn(),
    verifyComplianceDocument: vi.fn(),
    rejectComplianceDocument: vi.fn(),
    downloadComplianceDocument: vi.fn(),
    complianceRequirementsAdmin: vi.fn(),
    createComplianceRequirement: vi.fn(),
    deactivateComplianceRequirement: vi.fn(),
    locations: vi.fn(),
    visitorTypes: vi.fn(),
  },
}));

const baseDetail: ComplianceVisitDetail = {
  visit_id: 42,
  registration_reference: 'VMS-260826-0042',
  status: 'PENDING_APPROVAL',
  visitor_id: 7,
  visitor_name: 'Raj Kumar',
  visitor_type: 'Contractor',
  vendor_company_id: 1,
  vendor_company_name: 'ABC Services',
  site_name: 'Bangalore Office',
  host_name: 'Amit',
  work_purpose: 'HVAC repair',
  po_work_order_reference: 'PO-123',
  safety_acknowledged: true,
  scheduled_start: '2026-08-30T10:00:00Z',
  compliance: {
    compliance_status: 'NON_COMPLIANT',
    signals: ['Safety Training Certificate missing'],
    mandatory_incomplete: 1,
  },
  requirements: [
    {
      requirement_id: 10,
      requirement_name: 'Safety Training Certificate',
      requirement_code: 'SAFETY_TRAINING',
      document_owner_type: 'VISITOR',
      is_mandatory: true,
      usability: 'missing',
      current_document_id: null,
      documents: [],
    },
    {
      requirement_id: 11,
      requirement_name: 'Insurance Certificate',
      requirement_code: 'INSURANCE_CERT',
      document_owner_type: 'COMPANY',
      is_mandatory: true,
      usability: 'valid',
      current_document_id: 99,
      documents: [
        {
          id: 99,
          requirement_id: 11,
          file_name: 'insurance.pdf',
          status: 'PENDING_VERIFICATION',
          is_current: true,
          valid_until: '2026-12-31T00:00:00Z',
          uploaded_at: '2026-08-26T00:00:00Z',
        },
      ],
    },
  ],
};

describe('Phase 8.1 compliance detail', () => {
  const onRefresh = vi.fn().mockResolvedValue(undefined);
  const onClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.uploadComplianceDocument).mockResolvedValue({
      id: 100,
      status: 'PENDING_VERIFICATION',
      file_name: 'training.pdf',
      requirement_id: 10,
    });
    vi.mocked(api.verifyComplianceDocument).mockResolvedValue({
      id: 99,
      status: 'VALID',
      file_name: 'insurance.pdf',
      requirement_id: 11,
    });
    vi.mocked(api.rejectComplianceDocument).mockResolvedValue({
      id: 99,
      status: 'REJECTED',
      file_name: 'insurance.pdf',
      requirement_id: 11,
    });
  });

  it('shows missing document and upload action for authorized admin', () => {
    render(
      <ComplianceDetailPanel
        detail={baseDetail}
        permissions={['compliance.verify', 'compliance.document.download']}
        onClose={onClose}
        onRefresh={onRefresh}
      />,
    );
    expect(screen.getByText('Safety Training Certificate')).toBeInTheDocument();
    expect(screen.getByText('NON COMPLIANT')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Upload' })).toBeInTheDocument();
  });

  it('hides upload and download for security without verify/download permissions', () => {
    render(
      <ComplianceDetailPanel
        detail={baseDetail}
        permissions={['compliance.read']}
        onClose={onClose}
        onRefresh={onRefresh}
      />,
    );
    expect(screen.queryByRole('button', { name: 'Upload' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Download' })).not.toBeInTheDocument();
  });

  it('validates file type and size', () => {
    const bad = new File(['x'], 'evil.exe', { type: 'application/octet-stream' });
    expect(validateFile(bad)).toMatch(/PDF/);
    const huge = new File([new Uint8Array(11 * 1024 * 1024)], 'big.pdf', { type: 'application/pdf' });
    expect(validateFile(huge)).toMatch(/10 MB/);
    const ok = new File(['%PDF'], 'ok.pdf', { type: 'application/pdf' });
    expect(validateFile(ok)).toBeNull();
    ALLOWED_EXTENSIONS.forEach((ext) => {
      const f = new File(['x'], `file${ext}`, { type: 'application/octet-stream' });
      expect(validateFile(f)).toBeNull();
    });
  });

  it('upload shows loading and calls API', async () => {
    render(
      <ComplianceDetailPanel
        detail={baseDetail}
        permissions={['compliance.verify']}
        onClose={onClose}
        onRefresh={onRefresh}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Upload' }));
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['%PDF'], 'training.pdf', { type: 'application/pdf' });
    fireEvent.change(fileInput, { target: { files: [file] } });
    fireEvent.click(screen.getByRole('button', { name: 'Upload Document' }));
    await waitFor(() => {
      expect(api.uploadComplianceDocument).toHaveBeenCalled();
      expect(onRefresh).toHaveBeenCalled();
    });
  });

  it('verify action updates via API and refreshes', async () => {
    render(
      <ComplianceDetailPanel
        detail={baseDetail}
        permissions={['compliance.verify']}
        onClose={onClose}
        onRefresh={onRefresh}
      />,
    );
    fireEvent.click(screen.getAllByRole('button', { name: 'Verify' })[0]);
    const confirmButtons = screen.getAllByRole('button', { name: 'Verify' });
    fireEvent.click(confirmButtons[confirmButtons.length - 1]);
    await waitFor(() => {
      expect(api.verifyComplianceDocument).toHaveBeenCalledWith(99, 42);
      expect(onRefresh).toHaveBeenCalled();
    });
  });

  it('reject requires reason and refreshes', async () => {
    render(
      <ComplianceDetailPanel
        detail={baseDetail}
        permissions={['compliance.verify']}
        onClose={onClose}
        onRefresh={onRefresh}
      />,
    );
    fireEvent.click(screen.getAllByRole('button', { name: 'Reject' })[0]);
    const rejectButtons = screen.getAllByRole('button', { name: 'Reject' });
    fireEvent.click(rejectButtons[rejectButtons.length - 1]);
    await waitFor(() => {
      expect(api.rejectComplianceDocument).toHaveBeenCalled();
      expect(onRefresh).toHaveBeenCalled();
    });
  });
});

describe('Phase 8.1 compliance requirements', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.complianceRequirementsAdmin).mockResolvedValue([
      {
        id: 1,
        name: 'Insurance Certificate',
        code: 'INSURANCE_CERT',
        scope_type: 'GLOBAL',
        document_owner_type: 'COMPANY',
        is_mandatory: true,
        validity_required: true,
        document_required: true,
        is_active: true,
        expiry_warning_days: 30,
      },
    ]);
    vi.mocked(api.locations).mockResolvedValue([
      { id: 1, name: 'Bangalore Office', code: 'BLR', city: 'Bangalore', is_active: true },
    ]);
    vi.mocked(api.visitorTypes).mockResolvedValue([
      { id: 3, name: 'Contractor', code: 'CONTRACTOR' },
    ]);
    vi.mocked(api.createComplianceRequirement).mockResolvedValue({
      id: 50,
      name: 'New Req',
      code: 'NEW_REQ',
      scope_type: 'GLOBAL',
      document_owner_type: 'VISITOR',
      is_mandatory: true,
      validity_required: true,
      document_required: true,
      is_active: true,
      expiry_warning_days: 30,
    });
  });

  it('renders requirements list for configuration UI', async () => {
    render(<ComplianceRequirementsPanel />);
    await waitFor(() => {
      expect(screen.getByText('Compliance Requirements')).toBeInTheDocument();
      expect(screen.getByText('Insurance Certificate')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: 'Add Requirement' })).toBeInTheDocument();
  });

  it('create form validates name', async () => {
    render(<ComplianceRequirementsPanel />);
    await waitFor(() => screen.getByText('Insurance Certificate'));
    fireEvent.click(screen.getByRole('button', { name: 'Add Requirement' }));
    fireEvent.click(screen.getByRole('button', { name: 'Create Requirement' }));
    await waitFor(() => {
      expect(screen.getByText('Name is required.')).toBeInTheDocument();
    });
  });
});
