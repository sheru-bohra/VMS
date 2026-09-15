import type { ComplianceDocumentItem, ComplianceRequirementStatusItem, ComplianceSummary } from '../../types';

export function formatComplianceStatus(status: string): string {
  return status.replace(/_/g, ' ');
}

export function usabilityLabel(usability: string): string {
  switch (usability) {
    case 'valid': return 'Valid';
    case 'expiring': return 'Expiring';
    case 'expired': return 'Expired';
    case 'missing': return 'Missing';
    case 'pending': return 'Pending Verification';
    case 'rejected': return 'Rejected';
    default: return usability;
  }
}

export function usabilityClass(usability: string): string {
  switch (usability) {
    case 'valid': return 'status-badge status-badge--approved';
    case 'expiring': return 'status-badge status-badge--pending';
    case 'expired': return 'status-badge status-badge--rejected';
    case 'missing': return 'status-badge status-badge--rejected';
    case 'pending': return 'status-badge status-badge--pending';
    case 'rejected': return 'status-badge status-badge--rejected';
    default: return 'status-badge';
  }
}

export function complianceClass(status: string): string {
  switch (status) {
    case 'COMPLIANT': return 'status-badge status-badge--approved';
    case 'EXPIRING': return 'status-badge status-badge--pending';
    case 'REVIEW_REQUIRED': return 'status-badge status-badge--pending';
    case 'NON_COMPLIANT': return 'status-badge status-badge--rejected';
    default: return 'status-badge';
  }
}

export function parseComplianceSignals(summary: ComplianceSummary): string[] {
  const signals = summary.signals ?? [];
  const actionable = signals.filter(
    (s) => !s.startsWith('Valid:'),
  );
  return actionable.length ? actionable : [];
}

export function formatDateLabel(iso?: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return iso;
  }
}

export const REJECT_REASONS = [
  { id: 'incorrect', label: 'Incorrect document' },
  { id: 'unreadable', label: 'Unreadable document' },
  { id: 'expired', label: 'Expired document' },
  { id: 'wrong_owner', label: 'Wrong vendor/person' },
  { id: 'missing_info', label: 'Missing required information' },
  { id: 'other', label: 'Other' },
];

export const ALLOWED_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png'];
export const MAX_UPLOAD_MB = 10;

export function validateFile(file: File): string | null {
  const ext = file.name.includes('.') ? file.name.slice(file.name.lastIndexOf('.')).toLowerCase() : '';
  if (!ALLOWED_EXTENSIONS.includes(ext)) {
    return 'Only PDF, JPG, JPEG, and PNG files are allowed.';
  }
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
    return `File exceeds ${MAX_UPLOAD_MB} MB limit.`;
  }
  return null;
}

export type UploadTarget = {
  requirementId: number;
  requirementName: string;
  documentOwnerType: string;
  vendorCompanyId?: number;
  visitorId?: number;
  supersedesId?: number;
  visitId: number;
};

export function currentDocForRequirement(req: ComplianceRequirementStatusItem): ComplianceDocumentItem | undefined {
  if (!req.current_document_id) return undefined;
  return req.documents.find((d) => d.id === req.current_document_id);
}
