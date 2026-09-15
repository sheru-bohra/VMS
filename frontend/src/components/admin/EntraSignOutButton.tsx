import { useMsal } from '@azure/msal-react';
import { api } from '../../services/api';
import { entraConfig } from '../../config/auth';

export function EntraSignOutButton() {
  const { instance } = useMsal();

  const handleLogout = async () => {
    try {
      await api.authLogout();
    } catch {
      // continue local logout even if audit call fails
    }
    await instance.logoutRedirect({ postLogoutRedirectUri: entraConfig.postLogoutUri });
  };

  return (
    <button type="button" className="admin-btn admin-btn--sm" onClick={handleLogout} style={{ marginRight: '0.75rem' }}>
      Sign out
    </button>
  );
}
