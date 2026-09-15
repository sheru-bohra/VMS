import { PublicClientApplication, type Configuration } from '@azure/msal-browser';
import { entraConfig } from '../config/auth';

export function createMsalInstance(): PublicClientApplication | null {
  if (!entraConfig.tenantId || !entraConfig.clientId) {
    return null;
  }
  const config: Configuration = {
    auth: {
      clientId: entraConfig.clientId,
      authority: `https://login.microsoftonline.com/${entraConfig.tenantId}`,
      redirectUri: entraConfig.redirectUri,
      postLogoutRedirectUri: entraConfig.postLogoutUri,
      navigateToLoginRequestUrl: false,
    },
    cache: {
      cacheLocation: 'sessionStorage',
      storeAuthStateInCookie: false,
    },
  };
  return new PublicClientApplication(config);
}

export const msalInstance = createMsalInstance();
