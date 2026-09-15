import type { AdminRole } from '../types';

export function formatRoleLabel(role: AdminRole | string): string {
  const labels: Record<string, string> = {
    GLOBAL_ADMIN: 'Global Admin',
    HEAD_ADMIN: 'Head Admin',
    SITE_ADMIN: 'Site Admin',
    SECURITY: 'Security',
  };
  return labels[role] ?? role.replace(/_/g, ' ');
}

export function getInitials(displayName: string | null, email: string): string {
  const source = displayName?.trim() || email.split('@')[0];
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0].charAt(0)}${parts[1].charAt(0)}`.toUpperCase();
  }
  return source.slice(0, 2).toUpperCase();
}

export function formatAuthProvider(provider: string | null | undefined): string {
  if (!provider) return 'Development';
  if (provider === 'entra' || provider === 'microsoft') return 'Microsoft Entra';
  if (provider === 'vms_native' || provider === 'direct') return 'VMS Native';
  if (provider === 'dev') return 'Development';
  return provider;
}
