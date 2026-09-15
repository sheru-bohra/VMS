import type { PermissionKey } from '../types';
import { NAV_ITEMS, hasPermission } from './permissions';
import { roleHomePath } from '../config/auth';

export type ThemePreference = 'system' | 'light' | 'dark';
export type DensityPreference = 'comfortable' | 'compact';

export interface UserPreferences {
  theme: ThemePreference;
  density: DensityPreference;
  defaultLocationId: number | null;
  defaultLandingPage: string | null;
  reducedMotion: boolean;
}

export const DEFAULT_USER_PREFERENCES: UserPreferences = {
  theme: 'light',
  density: 'comfortable',
  defaultLocationId: null,
  defaultLandingPage: null,
  reducedMotion: false,
};

const STORAGE_PREFIX = 'vms:user-preferences:';
const RESOLVED_THEME_KEY = 'vms:staff-resolved-theme';

export function preferencesStorageKey(userId: number): string {
  return `${STORAGE_PREFIX}${userId}`;
}

export function loadUserPreferences(userId: number): UserPreferences {
  try {
    const raw = localStorage.getItem(preferencesStorageKey(userId));
    if (!raw) return { ...DEFAULT_USER_PREFERENCES };
    const parsed = JSON.parse(raw) as Partial<UserPreferences>;
    const theme =
      parsed.theme === 'light' || parsed.theme === 'dark' || parsed.theme === 'system'
        ? parsed.theme
        : DEFAULT_USER_PREFERENCES.theme;
    return {
      theme,
      density: parsed.density === 'compact' ? 'compact' : 'comfortable',
      defaultLocationId: parsed.defaultLocationId ?? null,
      defaultLandingPage: parsed.defaultLandingPage ?? null,
      reducedMotion: parsed.reducedMotion ?? false,
    };
  } catch {
    return { ...DEFAULT_USER_PREFERENCES };
  }
}

export function saveUserPreferences(userId: number, preferences: UserPreferences): void {
  localStorage.setItem(preferencesStorageKey(userId), JSON.stringify(preferences));
}

export function resetUserPreferences(userId: number): UserPreferences {
  saveUserPreferences(userId, { ...DEFAULT_USER_PREFERENCES });
  return { ...DEFAULT_USER_PREFERENCES };
}

export function resolveThemePreference(theme: ThemePreference): 'light' | 'dark' {
  if (theme === 'light' || theme === 'dark') return theme;
  if (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-color-scheme: dark)').matches
  ) {
    return 'dark';
  }
  return 'light';
}

export function persistResolvedTheme(resolved: 'light' | 'dark'): void {
  try {
    localStorage.setItem(RESOLVED_THEME_KEY, resolved);
  } catch {
    /* ignore */
  }
}

export function readBootResolvedTheme(): 'light' | 'dark' | null {
  try {
    const value = localStorage.getItem(RESOLVED_THEME_KEY);
    if (value === 'light' || value === 'dark') return value;
  } catch {
    /* ignore */
  }
  return null;
}

export const LANDING_PAGE_OPTIONS: Array<{
  path: string;
  label: string;
  permission?: PermissionKey;
}> = [
  { path: '/dashboard', label: 'Dashboard' },
  { path: '/visitors', label: 'Visitors', permission: 'visitor.read' },
  { path: '/expected-today', label: 'Expected Today', permission: 'arrival.read' },
  { path: '/onsite-now', label: 'Onsite Now', permission: 'onsite.read' },
  { path: '/approvals', label: 'Approvals', permission: 'approval.read' },
  { path: '/security-review', label: 'Security Review', permission: 'security_screening.read' },
  { path: '/reports', label: 'Reports', permission: 'reports.view' },
  { path: '/administration', label: 'Administration', permission: 'admins.read' },
];

export function getAllowedLandingPages(permissions: string[]): typeof LANDING_PAGE_OPTIONS {
  return LANDING_PAGE_OPTIONS.filter((opt) =>
    !opt.permission || hasPermission(permissions, opt.permission),
  );
}

export function isLandingPageAllowed(path: string, permissions: string[]): boolean {
  if (path === '/dashboard') return true;
  if (path === '/administration') {
    return NAV_ITEMS.find((i) => i.id === 'administration')?.anyPermissions?.some((p) =>
      permissions.includes(p),
    ) ?? false;
  }
  const match = LANDING_PAGE_OPTIONS.find((o) => o.path === path);
  if (!match) return false;
  if (!match.permission) return true;
  return hasPermission(permissions, match.permission);
}

export function getDefaultLandingPath(
  userId: number,
  permissions: string[],
  role: string,
): string {
  const prefs = loadUserPreferences(userId);
  if (
    prefs.defaultLandingPage &&
    isLandingPageAllowed(prefs.defaultLandingPage, permissions)
  ) {
    return prefs.defaultLandingPage;
  }
  return roleHomePath(role);
}

export function isLocationAllowed(
  locationId: number | null,
  allowedLocationIds: number[],
  canAccessAll: boolean,
): boolean {
  if (locationId === null) return canAccessAll;
  if (canAccessAll) return true;
  return allowedLocationIds.includes(locationId);
}
