import type { PublicVisitorType } from '../types';
import {
  getRegisterVisitorPolicy,
  isValidMobile,
  MOBILE_ERROR,
  type RegisterVisitorPolicy,
} from './registerVisitorPolicy';

export interface ValidationIssue {
  key: string;
  message: string;
  step: 1 | 2 | 3 | 4;
  fieldId?: string;
}

export interface RegisterVisitorFormState {
  fullName: string;
  mobile: string;
  email: string;
  company: string;
  visitorType: string;
  locationId: number | '';
  address: string;
  signatureData: string | null;
  govtIdType: string;
  govtIdNumber: string;
  policyAccepted: boolean;
  safetyInduction: boolean;
  purpose: string;
  visitDate: string;
  arrivalTime: string;
  departureTime: string;
  hostId: number | '';
  poReference: string;
  workPurpose: string;
  photoStaging: boolean;
}

export function validateRegisterVisitorForm(
  state: RegisterVisitorFormState,
  visitorType?: PublicVisitorType,
): ValidationIssue[] {
  const policy = getRegisterVisitorPolicy(state.visitorType, visitorType);
  const issues: ValidationIssue[] = [];

  if (!state.fullName.trim()) {
    issues.push({
      key: 'fullName',
      message: 'Full Name is required',
      step: 1,
      fieldId: 'field-fullName',
    });
  }

  if (!state.mobile.trim()) {
    issues.push({
      key: 'mobile',
      message: MOBILE_ERROR,
      step: 1,
      fieldId: 'field-mobile',
    });
  } else if (!isValidMobile(state.mobile)) {
    issues.push({
      key: 'mobile',
      message: MOBILE_ERROR,
      step: 1,
      fieldId: 'field-mobile',
    });
  }

  if (policy.emailRequired && !state.email.trim()) {
    issues.push({
      key: 'email',
      message: 'Email is required',
      step: 1,
      fieldId: 'field-email',
    });
  } else if (state.email.trim() && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(state.email.trim())) {
    issues.push({
      key: 'email',
      message: 'Enter a valid email address',
      step: 1,
      fieldId: 'field-email',
    });
  }

  if (policy.companyRequired && !state.company.trim()) {
    issues.push({
      key: 'company',
      message: 'Company Name is required',
      step: 1,
      fieldId: 'field-company',
    });
  }

  if (!state.visitorType) {
    issues.push({
      key: 'visitorType',
      message: 'Visitor Type is required',
      step: 1,
      fieldId: 'field-visitorType',
    });
  }

  if (!state.locationId) {
    issues.push({
      key: 'location',
      message: 'Location is required',
      step: 1,
      fieldId: 'field-location',
    });
  }

  if (policy.govtIdRequired) {
    if (!state.govtIdType) {
      issues.push({
        key: 'govtIdType',
        message: 'Government ID Type is required',
        step: 2,
        fieldId: 'field-govtIdType',
      });
    }
    if (!state.govtIdNumber.trim()) {
      issues.push({
        key: 'govtIdNumber',
        message: 'Government ID Number is required',
        step: 2,
        fieldId: 'field-govtIdNumber',
      });
    }
  }

  if (policy.signatureRequired && !state.signatureData) {
    issues.push({
      key: 'signature',
      message: 'Signature is required',
      step: 2,
      fieldId: 'field-signature',
    });
  }

  if (policy.safetyInductionRequired && !state.safetyInduction) {
    issues.push({
      key: 'safety',
      message: 'Safety Induction must be completed',
      step: 2,
      fieldId: 'field-safety',
    });
  }

  if (!state.policyAccepted) {
    issues.push({
      key: 'policy',
      message: 'Visitor Policy must be accepted',
      step: 2,
      fieldId: 'field-policy',
    });
  }

  if (policy.poWorkOrderRequired && !state.poReference.trim()) {
    issues.push({
      key: 'po',
      message: 'PO / Work Order Reference is required',
      step: 3,
      fieldId: 'field-po',
    });
  }

  if (policy.workPurposeRequired && !state.workPurpose.trim()) {
    issues.push({
      key: 'workPurpose',
      message: 'Work Purpose is required',
      step: 3,
      fieldId: 'field-workPurpose',
    });
  }

  if (!state.purpose.trim()) {
    issues.push({
      key: 'purpose',
      message: 'Purpose is required',
      step: 3,
      fieldId: 'field-purpose',
    });
  }

  if (!state.visitDate) {
    issues.push({
      key: 'visitDate',
      message: 'Visit Date is required',
      step: 3,
      fieldId: 'field-visitDate',
    });
  }

  if (!state.arrivalTime) {
    issues.push({
      key: 'arrivalTime',
      message: 'Expected Arrival is required',
      step: 3,
      fieldId: 'field-arrivalTime',
    });
  }

  if (!state.departureTime) {
    issues.push({
      key: 'departureTime',
      message: 'Expected Departure is required',
      step: 3,
      fieldId: 'field-departureTime',
    });
  } else if (
    state.arrivalTime &&
    state.departureTime &&
    state.departureTime <= state.arrivalTime
  ) {
    issues.push({
      key: 'times',
      message: 'Expected Departure must be after Expected Arrival',
      step: 3,
      fieldId: 'field-departureTime',
    });
  }

  if (policy.hostRequired && !state.hostId) {
    issues.push({
      key: 'host',
      message: 'Host is required',
      step: 3,
      fieldId: 'field-host',
    });
  }

  if (state.photoStaging) {
    issues.push({
      key: 'photo',
      message: 'Photo is still uploading',
      step: 1,
      fieldId: 'field-photo',
    });
  }

  return issues;
}

export function isStepComplete(
  step: 1 | 2 | 3 | 4,
  state: RegisterVisitorFormState,
  visitorType?: PublicVisitorType,
): boolean {
  const issues = validateRegisterVisitorForm(state, visitorType);
  if (step === 4) return issues.length === 0;
  return !issues.some((issue) => issue.step === step);
}

export function stepCompletion(
  state: RegisterVisitorFormState,
  visitorType?: PublicVisitorType,
): boolean[] {
  return [1, 2, 3, 4].map((step) =>
    isStepComplete(step as 1 | 2 | 3 | 4, state, visitorType),
  );
}

export function issuesForStep(
  issues: ValidationIssue[],
  step?: number,
): ValidationIssue[] {
  if (!step) return issues;
  return issues.filter((i) => i.step === step);
}

export function getPolicyForType(
  code: string,
  visitorType?: PublicVisitorType,
): RegisterVisitorPolicy {
  return getRegisterVisitorPolicy(code, visitorType);
}
