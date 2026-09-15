import { describe, expect, it } from 'vitest';
import {
  currentTimeInTimezone,
  getRegisterVisitorPolicy,
  isValidMobile,
  sanitizeMobileInput,
} from '../utils/registerVisitorPolicy';
import {
  isStepComplete,
  stepCompletion,
  validateRegisterVisitorForm,
  type RegisterVisitorFormState,
} from '../utils/registerVisitorValidation';

const baseState = (): RegisterVisitorFormState => ({
  fullName: 'Test Visitor',
  mobile: '9876543210',
  email: 'test@example.com',
  company: 'Acme Corp',
  visitorType: 'BUSINESS',
  locationId: 1,
  address: '',
  signatureData: null,
  govtIdType: '',
  govtIdNumber: '',
  policyAccepted: true,
  safetyInduction: false,
  purpose: 'Business Meeting',
  visitDate: '2099-01-15',
  arrivalTime: '10:00',
  departureTime: '11:00',
  hostId: 1,
  poReference: '',
  workPurpose: '',
  photoStaging: false,
});

describe('registerVisitorPolicy mobile validation', () => {
  it('accepts exactly 10 digits', () => {
    expect(isValidMobile('9876543210')).toBe(true);
  });

  it('rejects 9 digits', () => {
    expect(isValidMobile('987654321')).toBe(false);
  });

  it('rejects 11 digits', () => {
    expect(isValidMobile('98765432101')).toBe(false);
  });

  it('rejects letters', () => {
    expect(isValidMobile('98ABC43210')).toBe(false);
  });

  it('sanitizes pasted input to digits only', () => {
    expect(sanitizeMobileInput('98 7654 3210')).toBe('9876543210');
  });
});

describe('visitor type policies', () => {
  it('VIP hides government ID requirements', () => {
    const policy = getRegisterVisitorPolicy('VIP');
    expect(policy.govtIdRequired).toBe(false);
    expect(policy.showGovtIdSection).toBe(false);
    expect(policy.showPoWorkOrder).toBe(false);
    expect(policy.signatureRequired).toBe(false);
  });

  it('Business Visitor requires company not government ID', () => {
    const policy = getRegisterVisitorPolicy('BUSINESS');
    expect(policy.companyRequired).toBe(true);
    expect(policy.govtIdRequired).toBe(false);
  });

  it('Interview Candidate requires email', () => {
    const policy = getRegisterVisitorPolicy('INTERVIEW');
    expect(policy.emailRequired).toBe(true);
    expect(policy.govtIdRequired).toBe(false);
  });

  it('Delivery does not require host by default', () => {
    const policy = getRegisterVisitorPolicy('DELIVERY');
    expect(policy.hostRequired).toBe(false);
    expect(policy.govtIdRequired).toBe(false);
  });

  it('Vendor requires ID, signature, PO and work purpose', () => {
    const policy = getRegisterVisitorPolicy('VENDOR', {
      code: 'VENDOR',
      name: 'Vendor',
      requires_vendor_compliance: true,
      po_reference_required: true,
    });
    expect(policy.govtIdRequired).toBe(true);
    expect(policy.signatureRequired).toBe(true);
    expect(policy.poWorkOrderRequired).toBe(true);
    expect(policy.workPurposeRequired).toBe(true);
  });

  it('Contractor requires safety induction', () => {
    const policy = getRegisterVisitorPolicy('CONTRACTOR', {
      code: 'CONTRACTOR',
      name: 'Contractor',
      requires_vendor_compliance: true,
      po_reference_required: true,
    });
    expect(policy.safetyInductionRequired).toBe(true);
  });
});

describe('register visitor form validation', () => {
  it('valid Business Visitor passes without government ID', () => {
    const issues = validateRegisterVisitorForm(baseState(), {
      code: 'BUSINESS',
      name: 'Business Visitor',
    });
    expect(issues).toHaveLength(0);
  });

  it('blocks submit when policy not accepted', () => {
    const state = { ...baseState(), policyAccepted: false };
    const issues = validateRegisterVisitorForm(state);
    expect(issues.some((i) => i.key === 'policy')).toBe(true);
  });

  it('VIP minimal flow passes without company', () => {
    const state = {
      ...baseState(),
      visitorType: 'VIP',
      company: '',
      email: '',
    };
    const issues = validateRegisterVisitorForm(state, { code: 'VIP', name: 'VIP' });
    expect(issues.filter((i) => i.key === 'govtIdNumber')).toHaveLength(0);
    expect(issues.filter((i) => i.key === 'po')).toHaveLength(0);
    expect(issues).toHaveLength(0);
  });

  it('Vendor blocks without government ID', () => {
    const state = {
      ...baseState(),
      visitorType: 'VENDOR',
      company: 'test',
      poReference: 'PO-1',
      workPurpose: 'Install',
    };
    const issues = validateRegisterVisitorForm(state, {
      code: 'VENDOR',
      name: 'Vendor',
      requires_vendor_compliance: true,
      po_reference_required: true,
    });
    expect(issues.some((i) => i.key === 'govtIdNumber')).toBe(true);
    expect(issues.some((i) => i.key === 'signature')).toBe(true);
  });

  it('clears vendor requirements when type changes to VIP', () => {
    const vendorState = {
      ...baseState(),
      visitorType: 'VIP',
      company: '',
      govtIdType: '',
      govtIdNumber: '',
      poReference: '',
      workPurpose: '',
      signatureData: null,
      safetyInduction: false,
    };
    const issues = validateRegisterVisitorForm(vendorState, { code: 'VIP', name: 'VIP' });
    expect(issues.some((i) => i.key === 'govtIdNumber')).toBe(false);
    expect(issues.some((i) => i.key === 'po')).toBe(false);
    expect(issues).toHaveLength(0);
  });

  it('Vendor accepts unknown company name without vendor master match', () => {
    const state = {
      ...baseState(),
      visitorType: 'VENDOR',
      company: 'test',
      govtIdType: 'PASSPORT',
      govtIdNumber: 'AB1234567',
      signatureData: 'data:image/png;base64,abc',
      poReference: 'PO-1',
      workPurpose: 'Install',
      safetyInduction: true,
    };
    const issues = validateRegisterVisitorForm(state, {
      code: 'VENDOR',
      name: 'Vendor',
      requires_vendor_compliance: true,
      po_reference_required: true,
    });
    expect(issues.some((i) => i.key === 'vendorCompany')).toBe(false);
    expect(issues).toHaveLength(0);
  });

  it('requires company name when company is required', () => {
    const state = { ...baseState(), company: '' };
    const issues = validateRegisterVisitorForm(state, { code: 'BUSINESS', name: 'Business Visitor' });
    expect(issues.some((i) => i.key === 'company' && i.message === 'Company Name is required')).toBe(true);
  });

  it('Interview Candidate requires email', () => {
    const state = { ...baseState(), visitorType: 'INTERVIEW', email: '', company: '' };
    const issues = validateRegisterVisitorForm(state, { code: 'INTERVIEW', name: 'Interview Candidate' });
    expect(issues.some((i) => i.key === 'email')).toBe(true);
  });

  it('Vendor accepts unknown company without vendorCompany validation key', () => {
    const state = {
      ...baseState(),
      visitorType: 'VENDOR',
      company: 'test',
      govtIdType: 'PASSPORT',
      govtIdNumber: 'AB1234567',
      signatureData: 'data:image/png;base64,abc',
      poReference: 'PO-1',
      workPurpose: 'Install',
      safetyInduction: true,
    };
    const issues = validateRegisterVisitorForm(state, {
      code: 'VENDOR',
      name: 'Vendor',
      requires_vendor_compliance: true,
      po_reference_required: true,
    });
    expect(issues.some((i) => i.key === 'vendorCompany')).toBe(false);
  });
});

describe('step completion', () => {
  it('marks step 1 complete when personal fields valid', () => {
    expect(isStepComplete(1, baseState())).toBe(true);
  });

  it('VIP step 2 complete without government ID', () => {
    const state = { ...baseState(), visitorType: 'VIP', company: '' };
    expect(isStepComplete(2, state, { code: 'VIP', name: 'VIP' })).toBe(true);
  });

  it('Vendor step 2 incomplete without ID', () => {
    const state = {
      ...baseState(),
      visitorType: 'VENDOR',
      company: 'test',
      poReference: 'PO',
      workPurpose: 'Work',
    };
    expect(isStepComplete(2, state, {
      code: 'VENDOR',
      name: 'Vendor',
      requires_vendor_compliance: true,
      po_reference_required: true,
    })).toBe(false);
  });

  it('all steps complete when form valid', () => {
    const flags = stepCompletion(baseState());
    expect(flags).toEqual([true, true, true, true]);
  });
});

describe('expected arrival timezone helper', () => {
  it('returns HH:MM for Asia/Kolkata', () => {
    const value = currentTimeInTimezone('Asia/Kolkata');
    expect(value).toMatch(/^\d{2}:\d{2}$/);
  });
});

describe('Register Visitor page source', () => {
  it('removed vendor and designation fields', async () => {
    const { readFileSync } = await import('node:fs');
    const { dirname, resolve } = await import('node:path');
    const { fileURLToPath } = await import('node:url');
    const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
    const page = readFileSync(resolve(root, 'pages/register-visitor/RegisterVisitorPage.tsx'), 'utf8');
    expect(page).not.toContain('Designation');
    expect(page).not.toContain('Not a Vendor');
    expect(page).toContain('completedSteps');
    expect(page).toContain('validateRegisterVisitorForm');
    expect(page).toContain('sanitizeMobileInput');
  });
});
