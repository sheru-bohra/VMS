export const AUTH_MODE = (import.meta.env.VITE_AUTH_MODE as string | undefined) ?? 'dev';

export const isDevAuthMode = AUTH_MODE === 'dev';
export const isVmsNativeAuthMode = AUTH_MODE === 'vms_native';
export const isEntraAuthMode = AUTH_MODE === 'entra' || AUTH_MODE === 'vms_native';
export const isEntraOptional = AUTH_MODE === 'vms_native';
export const entraLoginEnabled =
  AUTH_MODE === 'entra' &&
  Boolean(import.meta.env.VITE_ENTRA_AUTH_ENABLED === 'true' || import.meta.env.VITE_ENTRA_TENANT_ID);

/** Microsoft Entra OIDC scopes — authentication only (no Graph). */
export const ENTRA_OIDC_SCOPES = ['openid', 'profile', 'email'] as const;

export const entraConfig = {
  tenantId: import.meta.env.VITE_ENTRA_TENANT_ID as string | undefined,
  clientId: import.meta.env.VITE_ENTRA_CLIENT_ID as string | undefined,
  redirectUri:
    (import.meta.env.VITE_ENTRA_REDIRECT_URI as string | undefined) ??
    `${window.location.origin}/auth/callback`,
  postLogoutUri:
    (import.meta.env.VITE_ENTRA_POST_LOGOUT_URI as string | undefined) ??
    `${window.location.origin}/login`,
};

export function entraConfigured(): boolean {
  return Boolean(entraConfig.tenantId && entraConfig.clientId);
}

export function roleHomePath(_role: string): string {
  return '/dashboard';
}

export function safeReturnPath(path: string | null | undefined): string | null {
  if (!path || !path.startsWith('/') || path.startsWith('//')) return null;
  if (path.includes(':') || path.includes('\\')) return null;
  const pathname = path.split('?')[0]?.split('#')[0] ?? path;
  if (
    pathname === '/login'
    || pathname.startsWith('/auth/')
    || pathname === '/visit'
    || pathname.startsWith('/visit/')
    || pathname.startsWith('/host/')
  ) {
    return null;
  }
  return path;
}
