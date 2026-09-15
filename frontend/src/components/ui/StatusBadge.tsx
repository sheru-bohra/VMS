import { formatStatus } from '../../types';

const STATUS_VARIANT: Record<string, string> = {
  PENDING_APPROVAL: 'pending',
  PENDING: 'pending',
  PENDING_VERIFICATION: 'pending',
  APPROVED: 'approved',
  EXPECTED: 'info',
  ARRIVED: 'info',
  CHECKED_IN: 'onsite',
  ONSITE: 'onsite',
  CHECKED_OUT: 'neutral',
  REJECTED: 'rejected',
  BLOCKED: 'rejected',
  CANCELLED: 'neutral',
  EXPIRED: 'neutral',
  OVERSTAYED: 'warning',
  REVIEW: 'warning',
  COMPLIANT: 'approved',
  NON_COMPLIANT: 'rejected',
  PROCESSING: 'info',
  FAILED: 'rejected',
  ACTIVE: 'approved',
  INACTIVE: 'neutral',
  VALID: 'approved',
  BROKEN: 'rejected',
};

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  const key = status.toUpperCase();
  const variant = STATUS_VARIANT[key] ?? 'neutral';
  const text = label ?? formatStatus(status);
  return <span className={`vms-status-badge vms-status-badge--${variant}`}>{text}</span>;
}
