import { safeReturnPath } from '../config/auth';
import { clearVmsNativeAccessToken } from './vmsNativeAuth';

const AUTH_MODE = (import.meta.env.VITE_AUTH_MODE as string | undefined) ?? 'dev';

export function getUnauthenticatedLoginRedirect(pathname: string, search = ''): string {
  const safe = safeReturnPath(`${pathname}${search}`);
  return safe ? `/login?returnTo=${encodeURIComponent(safe)}` : '/login';
}

export function isStaffAuthMode(): boolean {
  return AUTH_MODE === 'vms_native' || AUTH_MODE === 'entra' || AUTH_MODE === 'dev';
}

export function shouldRedirectUnauthenticatedToLogin(): boolean {
  return isStaffAuthMode();
}

export function shouldHandleApiUnauthorized(path: string): boolean {
  if (path === '/api/auth/login' || path === '/api/me' || path === '/api/health') {
    return false;
  }
  return AUTH_MODE === 'vms_native' || AUTH_MODE === 'entra';
}

export function handleApiUnauthorized(): void {
  if (typeof window === 'undefined') return;
  const current = window.location.pathname + window.location.search;
  if (current.startsWith('/login') || current.startsWith('/auth/callback')) {
    return;
  }
  clearVmsNativeAccessToken();
  window.location.replace(getUnauthenticatedLoginRedirect(window.location.pathname, window.location.search));
}
