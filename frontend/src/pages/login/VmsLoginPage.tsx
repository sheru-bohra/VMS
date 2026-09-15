import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  entraLoginEnabled,
  roleHomePath,
  safeReturnPath,
} from '../../config/auth';
import { PayULogo } from '../../components/branding/PayULogo';
import { useBootTheme } from '../../hooks/useBootTheme';
import { EntraMicrosoftLoginButton } from './EntraMicrosoftLoginButton';
import { setVmsNativeAccessToken } from '../../auth/vmsNativeAuth';
import { api, ApiClientError } from '../../services/api';
import '../../styles/login.css';

function PasswordVisibilityToggle({
  visible,
  onToggle,
}: {
  visible: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      className="login-form__password-toggle"
      onClick={onToggle}
      aria-label={visible ? 'Hide password' : 'Show password'}
      aria-pressed={visible}
      tabIndex={0}
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
        {visible ? (
          <>
            <path d="M3 3l18 18" strokeLinecap="round" />
            <path d="M10.58 10.58a2 2 0 0 0 2.84 2.84" strokeLinecap="round" />
            <path d="M9.88 5.09A10.94 10.94 0 0 1 12 5c5 0 9.27 3.11 11 7.5a11.8 11.8 0 0 1-2.05 3.32" strokeLinecap="round" />
            <path d="M6.61 6.61A11.8 11.8 0 0 0 1 12.5C2.73 16.89 7 20 12 20a10.9 10.9 0 0 0 2.12-.21" strokeLinecap="round" />
          </>
        ) : (
          <>
            <path d="M2 12.5C3.73 8.11 7.73 5 12.5 5S21.27 8.11 23 12.5C21.27 16.89 17.27 20 12.5 20S3.73 16.89 2 12.5Z" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx="12.5" cy="12.5" r="3" />
          </>
        )}
      </svg>
    </button>
  );
}

export function VmsLoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const resolvedTheme = useBootTheme();
  const [showError, setShowError] = useState(false);
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const returnTo = safeReturnPath(params.get('returnTo'));

  const handleLogin = async (event: React.FormEvent) => {
    event.preventDefault();
    if (loading) return;
    setLoading(true);
    setShowError(false);
    try {
      const result = await api.login(email.trim(), password);
      setVmsNativeAccessToken(result.access_token);
      const user = await api.me();
      if (user.force_password_change || result.force_password_change) {
        navigate('/auth/set-password', { replace: true });
        return;
      }
      navigate(returnTo ?? roleHomePath(user.role), { replace: true });
    } catch (err) {
      if (!(err instanceof ApiClientError) || err.status === 401 || err.status === 400) {
        setShowError(true);
      } else {
        setShowError(true);
      }
      setLoading(false);
    }
  };

  return (
    <div className="login-page" data-theme={resolvedTheme}>
      <div className="login-page__backdrop" aria-hidden="true" />
      <div className="login-page__content">
        <PayULogo variant="auth" />

        <div className="login-card">
          <header className="login-card__header">
            <h1 className="login-card__title">Welcome back</h1>
            <p className="login-card__subtitle">Sign in to your Visitor Management account.</p>
          </header>

          {showError && (
            <div className="login-card__error" role="alert" aria-live="polite">
              <p className="login-card__error-title">Unable to sign in</p>
              <p className="login-card__error-message">
                Please check your email and password and try again.
              </p>
            </div>
          )}

          <form className="login-form" onSubmit={handleLogin} noValidate>
            <label className="login-form__label" htmlFor="login-email">
              Corporate Email
              <input
                id="login-email"
                type="email"
                className="login-form__input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                autoComplete="username"
                required
                disabled={loading}
              />
            </label>

            <label className="login-form__label" htmlFor="login-password">
              Password
              <div className="login-form__password-field">
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  className="login-form__input login-form__input--password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  autoComplete="current-password"
                  required
                  disabled={loading}
                />
                <PasswordVisibilityToggle
                  visible={showPassword}
                  onToggle={() => setShowPassword((value) => !value)}
                />
              </div>
            </label>

            <button type="submit" className="login-card__btn login-card__btn--primary" disabled={loading}>
              {loading ? (
                <span className="login-card__btn-content">
                  <span className="login-card__spinner" aria-hidden="true" />
                  Signing in…
                </span>
              ) : (
                'Sign In'
              )}
            </button>
          </form>

          {entraLoginEnabled && <EntraMicrosoftLoginButton disabled={loading} onError={() => setShowError(true)} />}

          <p className="login-card__security">
            <span className="login-card__security-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
                <path
                  d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </span>
            Authorized staff access only
          </p>
        </div>

        <footer className="login-page__footer">
          PayU Visitor Management • Authorized access only
        </footer>
      </div>
    </div>
  );
}
