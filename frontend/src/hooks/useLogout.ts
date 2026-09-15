import { api } from '../services/api';
import { clearVmsNativeAccessToken } from '../auth/vmsNativeAuth';
import { entraConfig } from '../config/auth';

const DEV_USER_KEY = 'vms_dev_user';

export function clearDevAuthIdentity(): void {
  localStorage.removeItem(DEV_USER_KEY);
}

export function setDevAuthIdentity(email: string): void {
  localStorage.setItem(DEV_USER_KEY, email);
}

export async function performVmsNativeLogout(navigate: (path: string, opts?: { replace?: boolean }) => void): Promise<void> {
  try {
    await api.authLogout();
  } catch {
    /* continue logout */
  }
  clearVmsNativeAccessToken();
  navigate('/login', { replace: true });
}

export async function performEntraLogout(
  msalInstance: {
    logoutRedirect: (opts: { postLogoutRedirectUri: string }) => Promise<void>;
  },
  authProvider?: string | null,
  navigate?: (path: string, opts?: { replace?: boolean }) => void,
): Promise<void> {
  if ((authProvider === 'vms_native' || authProvider === 'direct') && navigate) {
    await performVmsNativeLogout(navigate);
    return;
  }
  try {
    await api.authLogout();
  } catch {
    /* continue logout */
  }
  clearVmsNativeAccessToken();
  await msalInstance.logoutRedirect({ postLogoutRedirectUri: entraConfig.postLogoutUri });
}

