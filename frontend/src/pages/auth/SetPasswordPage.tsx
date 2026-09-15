import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { roleHomePath } from '../../config/auth';
import { getVmsNativeAccessToken } from '../../auth/vmsNativeAuth';
import { api, ApiClientError } from '../../services/api';
import '../../styles/login.css';

export function SetPasswordPage() {
  const navigate = useNavigate();

  useEffect(() => {
    if (!getVmsNativeAccessToken()) {
      navigate('/login', { replace: true });
    }
  }, [navigate]);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.setPassword(newPassword, confirmPassword);
      const user = await api.me();
      navigate(roleHomePath(user.role), { replace: true });
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(err.message);
      } else {
        setError('Unable to set your new password. Please try again.');
      }
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <h1 className="login-card__title">Set your new password</h1>
        <p className="login-card__subtitle">Choose a secure password with at least 12 characters.</p>
        {error && <p className="login-card__error" role="alert">{error}</p>}
        <form className="login-form" onSubmit={handleSubmit}>
          <label className="login-form__label">
            New Password
            <input
              type="password"
              className="login-form__input"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete="new-password"
              minLength={12}
              required
            />
          </label>
          <label className="login-form__label">
            Confirm Password
            <input
              type="password"
              className="login-form__input"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
              minLength={12}
              required
            />
          </label>
          <button type="submit" className="login-card__btn" disabled={loading}>
            Save Password
          </button>
        </form>
      </div>
    </div>
  );
}
