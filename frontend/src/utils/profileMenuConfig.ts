import type { PermissionKey } from '../types';
import { hasPermission } from './permissions';

export interface ProfileAdminLink {
  label: string;
  path: string;
  permission: PermissionKey;
}

export const PROFILE_ADMIN_LINKS: ProfileAdminLink[] = [
  { label: 'Users & Access', path: '/administration/users', permission: 'admins.read' },
  { label: 'Privacy & Security', path: '/administration/privacy-security', permission: 'privacy.retention.read' },
  { label: 'Access & Badge Administration', path: '/administration/access-badges', permission: 'access.config.read' },
  { label: 'Operations Readiness', path: '/administration/operations-readiness', permission: 'operations.readiness.read' },
];

export function getProfileAdminLinks(permissions: string[]): ProfileAdminLink[] {
  return PROFILE_ADMIN_LINKS.filter((link) => hasPermission(permissions, link.permission));
}

export const DEV_TEST_USERS: Array<{ email: string; label: string }> = [
  { email: 'sheru.bohra@lazypay.in', label: 'Global Admin (Owner)' },
  { email: 'headadmin@vms.local', label: 'Head Admin' },
  { email: 'siteadmin.blr@vms.local', label: 'Site Admin — Bangalore' },
  { email: 'siteadmin.mum@vms.local', label: 'Site Admin — Mumbai' },
  { email: 'security.blr@vms.local', label: 'Security — Bangalore' },
  { email: 'security.mum@vms.local', label: 'Security — Mumbai' },
];
