import { useEffect } from 'react';
import { useMsal } from '@azure/msal-react';
import { setAccessTokenProvider } from '../services/api';
import { ENTRA_OIDC_SCOPES } from '../config/auth';

export function MsalAuthBridge({ children }: { children: React.ReactNode }) {
  const { instance, accounts } = useMsal();

  useEffect(() => {
    setAccessTokenProvider(async () => {
      const account = instance.getActiveAccount() ?? accounts[0];
      if (!account) return null;
      try {
        const result = await instance.acquireTokenSilent({
          scopes: [...ENTRA_OIDC_SCOPES],
          account,
        });
        return result.idToken ?? null;
      } catch {
        return null;
      }
    });
  }, [instance, accounts]);

  return <>{children}</>;
}
