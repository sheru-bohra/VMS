import type { DashboardData } from '../../types';

export interface AttentionItem {
  message: string;
  href: string;
  severity: 'info' | 'warning' | 'critical';
}

export function buildDashboardAttention(data: DashboardData): AttentionItem | null {
  const kpis = data.kpis;
  const critical: AttentionItem[] = [];
  const warning: AttentionItem[] = [];
  const info: AttentionItem[] = [];

  if ((data.active_emergencies?.length ?? 0) > 0) {
    critical.push({
      message: `${data.active_emergencies.length} active emergency event(s) require attention.`,
      href: '/emergency-roll-call',
      severity: 'critical',
    });
  }

  if (kpis.overstayed > 0) {
    warning.push({
      message: `${kpis.overstayed} visitor(s) may have overstayed their visit.`,
      href: '/onsite-now',
      severity: 'warning',
    });
  }

  if (kpis.awaiting_approval > 0) {
    warning.push({
      message: `${kpis.awaiting_approval} visitor registration(s) awaiting approval.`,
      href: '/approvals',
      severity: 'warning',
    });
  }

  if (data.security_summary?.review > 0) {
    warning.push({
      message: `${data.security_summary.review} security review(s) pending.`,
      href: '/security-review',
      severity: 'warning',
    });
  }

  if (data.compliance_summary?.non_compliant > 0) {
    warning.push({
      message: `${data.compliance_summary.non_compliant} non-compliant vendor record(s).`,
      href: '/vendors-contractors',
      severity: 'warning',
    });
  }

  if (critical.length > 0) return critical[0];
  if (warning.length > 0) return warning[0];
  if (info.length > 0) return info[0];
  return null;
}
