import type { PermissionKey } from '../types';
import {
  DASHBOARD_NAV,
  NAV_GROUPS,
  REGISTER_VISITOR_NAV,
  type NavChildConfig,
  type NavGroupConfig,
} from './navigationConfig';

export type NavItemConfig = NavChildConfig;

function childAllowed(item: NavChildConfig, permissions: string[]): boolean {
  if (item.anyPermissions?.length) {
    return item.anyPermissions.some((p) => permissions.includes(p));
  }
  if (!item.requiredPermission) return true;
  return permissions.includes(item.requiredPermission);
}

export function filterNavChildByPermissions(
  permissions: string[],
  item: NavChildConfig,
): boolean {
  return childAllowed(item, permissions);
}

export function filterNavGroupsByPermissions(permissions: string[]): NavGroupConfig[] {
  return NAV_GROUPS
    .map((group) => ({
      ...group,
      children: group.children.filter((child) => childAllowed(child, permissions)),
    }))
    .filter((group) => group.children.length > 0);
}

export function filterDashboardNav(_permissions: string[]): NavChildConfig | null {
  return DASHBOARD_NAV;
}

export function filterRegisterVisitorNav(permissions: string[]): NavChildConfig | null {
  if (!permissions.includes('invitation.create')) return null;
  return REGISTER_VISITOR_NAV;
}

/** Flat nav list — backward compatibility for permission tests and preferences */
export const NAV_ITEMS: Array<{
  id: string;
  label: string;
  path: string;
  icon: string;
  requiredPermission?: PermissionKey;
  anyPermissions?: PermissionKey[];
}> = [
  {
    id: DASHBOARD_NAV.id,
    label: DASHBOARD_NAV.label,
    path: DASHBOARD_NAV.path,
    icon: DASHBOARD_NAV.icon,
  },
  {
    id: REGISTER_VISITOR_NAV.id,
    label: REGISTER_VISITOR_NAV.label,
    path: REGISTER_VISITOR_NAV.path,
    icon: REGISTER_VISITOR_NAV.icon,
    requiredPermission: REGISTER_VISITOR_NAV.requiredPermission,
  },
  ...NAV_GROUPS.flatMap((group) =>
    group.children.map((child) => ({
      id: child.id,
      label: child.label,
      path: child.path,
      icon: child.icon,
      requiredPermission: child.requiredPermission,
      anyPermissions: child.anyPermissions,
    })),
  ),
];

export function filterNavByPermissions(
  permissions: string[],
  items = NAV_ITEMS,
): typeof NAV_ITEMS {
  return items.filter((item) => {
    if (item.anyPermissions?.length) {
      return item.anyPermissions.some((p) => permissions.includes(p));
    }
    if (!item.requiredPermission) return true;
    return permissions.includes(item.requiredPermission);
  });
}

export function hasPermission(permissions: string[], permission: PermissionKey): boolean {
  return permissions.includes(permission);
}
