import { useMsal } from '@azure/msal-react';
import { entraConfig, entraConfigured, ENTRA_OIDC_SCOPES } from '../../config/auth';

export function EntraMicrosoftLoginButton({
  disabled,
  onError,
}: {
  disabled?: boolean;
  onError: (message: string) => void;
}) {
  const { instance } = useMsal();

  if (!entraConfigured()) {
    return null;
  }

  const handleMicrosoftLogin = async () => {
    onError('');
    try {
      await instance.loginRedirect({
        scopes: [...ENTRA_OIDC_SCOPES],
        redirectUri: entraConfig.redirectUri,
      });
    } catch {
      onError("We couldn't complete Microsoft authentication. Please try again.");
    }
  };

  return (
    <>
      <div className="login-divider">
        <span>or</span>
      </div>
      <button
        type="button"
        className="login-card__btn login-card__btn--microsoft"
        onClick={handleMicrosoftLogin}
        disabled={disabled}
      >
        Continue with Microsoft
      </button>
    </>
  );
}
