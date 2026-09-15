import type { PublicVisitorType } from '../types';

export const MOBILE_PATTERN = /^[0-9]{10}$/;
export const MOBILE_ERROR = 'Enter a valid 10-digit mobile number.';

export interface RegisterVisitorPolicy {
  companyRequired: boolean;
  emailRequired: boolean;
  hostRequired: boolean;
  govtIdRequired: boolean;
  signatureRequired: boolean;
  poWorkOrderRequired: boolean;
  workPurposeRequired: boolean;
  safetyInductionRequired: boolean;
  showGovtIdSection: boolean;
  showSignature: boolean;
  showPoWorkOrder: boolean;
  showWorkPurpose: boolean;
  showNda: boolean;
  showPpe: boolean;
  showSafetyInduction: boolean;
  showCompany: boolean;
  requiresVendorMatch: boolean;
  idStepInfoMessage?: string;
}

const WORKSITE_CODES = new Set(['VENDOR', 'CONTRACTOR', 'SERVICE']);

function baseLowFriction(overrides: Partial<RegisterVisitorPolicy>): RegisterVisitorPolicy {
  return {
    companyRequired: false,
    emailRequired: false,
    hostRequired: true,
    govtIdRequired: false,
    signatureRequired: false,
    poWorkOrderRequired: false,
    workPurposeRequired: false,
    safetyInductionRequired: false,
    showGovtIdSection: false,
    showSignature: false,
    showPoWorkOrder: false,
    showWorkPurpose: false,
    showNda: false,
    showPpe: false,
    showSafetyInduction: false,
    showCompany: true,
    requiresVendorMatch: false,
    idStepInfoMessage:
      'No additional identity documents are required for this visitor type.',
    ...overrides,
  };
}

export function getRegisterVisitorPolicy(
  code: string,
  visitorType?: PublicVisitorType,
): RegisterVisitorPolicy {
  const requiresVendor =
    visitorType?.requires_vendor_compliance ?? WORKSITE_CODES.has(code);
  const poFromDb = visitorType?.po_reference_required ?? ['VENDOR', 'CONTRACTOR'].includes(code);
  const poRequired = poFromDb || code === 'SERVICE';

  switch (code) {
    case 'BUSINESS':
      return baseLowFriction({
        companyRequired: true,
        showCompany: true,
      });
    case 'PARTNER':
      return baseLowFriction({
        companyRequired: true,
        showCompany: true,
      });
    case 'VIP':
      return baseLowFriction({
        showCompany: true,
        companyRequired: false,
      });
    case 'INTERVIEW':
      return baseLowFriction({
        emailRequired: true,
        companyRequired: false,
        showCompany: true,
      });
    case 'DELIVERY':
      return baseLowFriction({
        hostRequired: false,
        companyRequired: false,
        showCompany: true,
      });
    case 'EVENT':
      return baseLowFriction({
        companyRequired: false,
        showCompany: true,
      });
    case 'OTHER':
      return baseLowFriction({
        companyRequired: false,
        showCompany: true,
      });
    case 'VENDOR':
      return {
        companyRequired: true,
        emailRequired: false,
        hostRequired: true,
        govtIdRequired: true,
        signatureRequired: true,
        poWorkOrderRequired: poRequired,
        workPurposeRequired: true,
        safetyInductionRequired: requiresVendor,
        showGovtIdSection: true,
        showSignature: true,
        showPoWorkOrder: poRequired,
        showWorkPurpose: true,
        showNda: true,
        showPpe: true,
        showSafetyInduction: true,
        showCompany: true,
        requiresVendorMatch: true,
      };
    case 'CONTRACTOR':
      return {
        companyRequired: true,
        emailRequired: false,
        hostRequired: true,
        govtIdRequired: true,
        signatureRequired: true,
        poWorkOrderRequired: poRequired,
        workPurposeRequired: true,
        safetyInductionRequired: true,
        showGovtIdSection: true,
        showSignature: true,
        showPoWorkOrder: poRequired,
        showWorkPurpose: true,
        showNda: true,
        showPpe: true,
        showSafetyInduction: true,
        showCompany: true,
        requiresVendorMatch: true,
      };
    case 'SERVICE':
      return {
        companyRequired: true,
        emailRequired: false,
        hostRequired: true,
        govtIdRequired: true,
        signatureRequired: true,
        poWorkOrderRequired: poRequired,
        workPurposeRequired: true,
        safetyInductionRequired: true,
        showGovtIdSection: true,
        showSignature: true,
        showPoWorkOrder: poRequired,
        showWorkPurpose: true,
        showNda: true,
        showPpe: true,
        showSafetyInduction: true,
        showCompany: true,
        requiresVendorMatch: true,
      };
    default:
      return baseLowFriction({});
  }
}

export function sanitizeMobileInput(value: string): string {
  return value.replace(/\D/g, '').slice(0, 10);
}

export function isValidMobile(value: string): boolean {
  return MOBILE_PATTERN.test(value.trim());
}

export function currentTimeInTimezone(timezone: string): string {
  const tz = timezone || 'Asia/Kolkata';
  try {
    const parts = new Intl.DateTimeFormat('en-GB', {
      timeZone: tz,
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).formatToParts(new Date());
    const hour = parts.find((p) => p.type === 'hour')?.value ?? '09';
    const minute = parts.find((p) => p.type === 'minute')?.value ?? '00';
    return `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`;
  } catch {
    const now = new Date();
    return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  }
}

export function locationTimezone(
  location?: { timezone?: string | null; code?: string },
): string {
  if (location?.timezone) return location.timezone;
  if (location?.code === 'BLR' || location?.code === 'MUM') return 'Asia/Kolkata';
  return 'Asia/Kolkata';
}
