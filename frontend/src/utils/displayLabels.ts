/** Friendly display labels for machine identifiers (backend values unchanged). */

export const RETENTION_CATEGORY_LABELS: Record<string, string> = {
  AI_INTERACTION: 'AI Interaction',
  EMERGENCY_SNAPSHOT_PII: 'Emergency Snapshot PII',
  NOTIFICATION_CONTENT: 'Notification Content',
  VISITOR_PII: 'Visitor PII',
  VISIT_FREE_TEXT: 'Visit Free Text',
  AUDIT_EVENT: 'Audit Event',
  ACCESS_CREDENTIAL: 'Access Credential',
};

export const RETENTION_ACTION_LABELS: Record<string, string> = {
  PURGE_CONTENT: 'Purge Content',
  ANONYMIZE: 'Anonymize',
  ARCHIVE: 'Archive',
};

export function formatRetentionCategory(code: string): string {
  return RETENTION_CATEGORY_LABELS[code] ?? code.replace(/_/g, ' ');
}

export function formatRetentionAction(action: string): string {
  return RETENTION_ACTION_LABELS[action] ?? action.replace(/_/g, ' ');
}

export function formatReadinessStatus(status: string): string {
  const upper = status.toUpperCase();
  if (upper === 'OK' || upper === 'PASS' || upper === 'READY') return 'Ready';
  if (upper === 'WARN' || upper === 'WARNING') return 'Attention';
  if (upper === 'FAIL' || upper === 'ERROR' || upper === 'BROKEN') return 'Failed';
  return status;
}
