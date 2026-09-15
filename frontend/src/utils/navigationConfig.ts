import type { PermissionKey } from '../types';

export type NavIconName =
  | 'layout-dashboard'
  | 'users'
  | 'clock'
  | 'user-check'
  | 'mail'
  | 'clipboard-list'
  | 'qr-code'
  | 'check-circle'
  | 'shield-alert'
  | 'shield-check'
  | 'triangle-alert'
  | 'key-round'
  | 'building-2'
  | 'bar-chart'
  | 'sparkles'
  | 'settings'
  | 'map-pin'
  | 'lock'
  | 'badge'
  | 'activity'
  | 'users-round'
  | 'shield'
  | 'briefcase'
  | 'chart-line'
  | 'sliders'
  | 'user-round-plus';

export type NavIconTone =
  | 'indigo'
  | 'blue'
  | 'cyan'
  | 'green'
  | 'violet'
  | 'teal'
  | 'amber'
  | 'orange'
  | 'red'
  | 'purple'
  | 'slate'
  | 'emerald';

export interface NavChildConfig {
  id: string;
  label: string;
  path: string;
  icon: NavIconName;
  iconTone: NavIconTone;
  requiredPermission?: PermissionKey;
  anyPermissions?: PermissionKey[];
}

export interface NavGroupConfig {
  id: string;
  label: string;
  icon: NavIconName;
  iconTone: NavIconTone;
  children: NavChildConfig[];
}

export const DASHBOARD_NAV: NavChildConfig = {
  id: 'dashboard',
  label: 'Dashboard',
  path: '/dashboard',
  icon: 'layout-dashboard',
  iconTone: 'indigo',
};

export const REGISTER_VISITOR_NAV: NavChildConfig = {
  id: 'register-visitor',
  label: 'Register Visitor',
  path: '/register-visitor',
  icon: 'user-round-plus',
  iconTone: 'violet',
  requiredPermission: 'invitation.create',
};

export const NAV_GROUPS: NavGroupConfig[] = [
  {
    id: 'visitor-operations',
    label: 'Visitor Operations',
    icon: 'users-round',
    iconTone: 'blue',
    children: [
      { id: 'visitors', label: 'Visitors', path: '/visitors', icon: 'users', iconTone: 'blue', requiredPermission: 'visitor.read' },
      { id: 'expected', label: 'Expected Today', path: '/expected-today', icon: 'clock', iconTone: 'cyan', requiredPermission: 'arrival.read' },
      { id: 'onsite', label: 'Onsite Now', path: '/onsite-now', icon: 'user-check', iconTone: 'green', requiredPermission: 'onsite.read' },
      { id: 'invitations', label: 'Invitations', path: '/invitations', icon: 'mail', iconTone: 'violet', requiredPermission: 'invitation.read' },
      { id: 'registrations', label: 'Self Registrations', path: '/self-registrations', icon: 'clipboard-list', iconTone: 'teal', requiredPermission: 'registration.read' },
      { id: 'approvals', label: 'Approvals', path: '/approvals', icon: 'check-circle', iconTone: 'amber', requiredPermission: 'approval.read' },
    ],
  },
  {
    id: 'security-access',
    label: 'Security & Access',
    icon: 'shield',
    iconTone: 'orange',
    children: [
      { id: 'watchlist', label: 'Watchlist', path: '/watchlist', icon: 'shield-alert', iconTone: 'orange', requiredPermission: 'watchlist.read' },
      { id: 'security-review', label: 'Security Review', path: '/security-review', icon: 'shield-check', iconTone: 'amber', requiredPermission: 'security_screening.read' },
      { id: 'access-operations', label: 'Access Operations', path: '/access-operations', icon: 'key-round', iconTone: 'cyan', requiredPermission: 'access.read' },
    ],
  },
  {
    id: 'vendors-compliance',
    label: 'Vendors & Compliance',
    icon: 'briefcase',
    iconTone: 'purple',
    children: [
      { id: 'vendors', label: 'Vendors & Contractors', path: '/vendors-contractors', icon: 'building-2', iconTone: 'purple', requiredPermission: 'vendor_company.read' },
    ],
  },
  {
    id: 'insights',
    label: 'Insights',
    icon: 'chart-line',
    iconTone: 'indigo',
    children: [
      { id: 'reports', label: 'Reports', path: '/reports', icon: 'bar-chart', iconTone: 'blue', requiredPermission: 'reports.view' },
      { id: 'vms-copilot', label: 'VMS Copilot', path: '/vms-copilot', icon: 'sparkles', iconTone: 'violet', requiredPermission: 'ai.copilot.use' },
    ],
  },
  {
    id: 'system-administration',
    label: 'System Administration',
    icon: 'sliders',
    iconTone: 'slate',
    children: [
      {
        id: 'administration',
        label: 'Administration Home',
        path: '/administration',
        icon: 'settings',
        iconTone: 'slate',
        anyPermissions: ['admins.read', 'privacy.retention.read', 'access.config.read', 'operations.readiness.read'],
      },
      { id: 'locations', label: 'Locations', path: '/locations', icon: 'map-pin', iconTone: 'teal', requiredPermission: 'locations.read' },
      { id: 'privacy-security', label: 'Privacy & Security', path: '/administration/privacy-security', icon: 'lock', iconTone: 'emerald', requiredPermission: 'privacy.retention.read' },
      { id: 'access-badges-admin', label: 'Access & Badges', path: '/administration/access-badges', icon: 'badge', iconTone: 'violet', requiredPermission: 'access.config.read' },
      { id: 'operations-readiness', label: 'Operations Readiness', path: '/administration/operations-readiness', icon: 'activity', iconTone: 'green', requiredPermission: 'operations.readiness.read' },
    ],
  },
];

const ADMIN_CHILD_PATHS = NAV_GROUPS
  .find((g) => g.id === 'system-administration')
  ?.children.map((c) => c.path)
  .filter((p) => p !== '/administration') ?? [];

export function isNavChildActive(pathname: string, item: NavChildConfig): boolean {
  if (pathname === item.path) return true;

  if (item.path === '/administration') {
    if (pathname === '/administration') return true;
    if (pathname.startsWith('/administration/')) {
      return !ADMIN_CHILD_PATHS.some(
        (p) => pathname === p || pathname.startsWith(`${p}/`),
      );
    }
    return false;
  }

  if (item.path === '/vendors-contractors') {
    return pathname.startsWith('/vendors-contractors') || pathname.startsWith('/vendors');
  }

  return pathname.startsWith(`${item.path}/`);
}

export function findActiveGroupId(pathname: string, groups: NavGroupConfig[]): string | undefined {
  for (const group of groups) {
    if (group.children.some((child) => isNavChildActive(pathname, child))) {
      return group.id;
    }
  }
  return undefined;
}

export function findActiveChildId(pathname: string, groups: NavGroupConfig[]): string | undefined {
  for (const group of groups) {
    for (const child of group.children) {
      if (isNavChildActive(pathname, child)) return child.id;
    }
  }
  return undefined;
}
