import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useMsal } from '@azure/msal-react';
import { roleHomePath, safeReturnPath } from '../../config/auth';
import { api, ApiClientError } from '../../services/api';
import '../../styles/login.css';

export function AuthCallbackPage() {
  const { instance } = useMsal();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await instance.handleRedirectPromise();
        const account = result?.account ?? instance.getAllAccounts()[0];
        if (account) {
          instance.setActiveAccount(account);
        }
        const user = await api.me();
        if (cancelled) return;
        const returnTo = safeReturnPath(params.get('returnTo'));
        navigate(returnTo ?? roleHomePath(user.role), { replace: true });
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiClientError) {
          if (err.code === 'VMS_USER_NOT_AUTHORIZED') {
            setError(
              'Your Microsoft account is valid, but you are not authorized to access the Visitor Management System.',
            );
          } else if (err.code === 'VMS_USER_INACTIVE') {
            setError('Your VMS access has been disabled. Please contact the VMS administrator.');
          } else if (err.code === 'AUTH_WRONG_TENANT') {
            setError('This Microsoft account does not belong to an authorized organization.');
          } else {
            setError("We couldn't complete Microsoft authentication. Please try again.");
          }
        } else {
          setError("We couldn't complete Microsoft authentication. Please try again.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [instance, navigate, params]);

  return (
    <div className="login-page">
      <div className="login-card">
        <h1 className="login-card__title">Signing you in…</h1>
        {error ? (
          <>
            <p className="login-card__error" role="alert">{error}</p>
            <button type="button" className="login-card__btn" onClick={() => navigate('/login', { replace: true })}>
              Back to sign in
            </button>
          </>
        ) : (
          <p className="login-card__subtitle">Completing Microsoft authentication…</p>
        )}
      </div>
    </div>
  );
}
