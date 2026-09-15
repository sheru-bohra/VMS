import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { LoadingState } from '../../components/StatePanels';
import { hasPermission } from '../../utils/permissions';
import { api, ApiClientError } from '../../services/api';
import { clearVmsNativeAccessToken } from '../../auth/vmsNativeAuth';
import {
  formatAuthProvider,
  formatRoleLabel,
  getInitials,
} from '../../utils/userDisplay';
import {
  getCapabilityGroups,
  getRoleDescription,
} from '../../utils/capabilities';
import '../../styles/admin-pages.css';
import '../../styles/profile-pages.css';

function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function ProfilePage() {
  const { user, loading, reload } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [section, setSection] = useState<'profile' | 'access' | 'password'>('profile');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);
  const [passwordSaving, setPasswordSaving] = useState(false);

  useEffect(() => {
    if (location.hash === '#access') {
      setSection('access');
    } else if (location.hash === '#password') {
      setSection('password');
    } else {
      setSection('profile');
    }
  }, [location.hash]);

  const canChangePassword = user?.role === 'GLOBAL_ADMIN' && user?.auth_provider === 'vms_native';

  const handlePasswordChange = async (event: React.FormEvent) => {
    event.preventDefault();
    setPasswordError(null);
    setPasswordSuccess(null);
    setPasswordSaving(true);
    try {
      await api.changePassword(currentPassword, newPassword, confirmPassword);
      setPasswordSuccess('Password updated. Sign in again with your new password.');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      clearVmsNativeAccessToken();
      await reload();
      window.setTimeout(() => navigate('/login', { replace: true }), 1500);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setPasswordError(err.message);
      } else {
        setPasswordError('Unable to change password. Please try again.');
      }
    } finally {
      setPasswordSaving(false);
    }
  };

  if (loading || !user) {
    return <LoadingState message="Loading profile…" />;
  }

  const displayName = user.display_name ?? user.email.split('@')[0];
  const canAccessAll = hasPermission(user.permissions, 'locations.read');
  const capabilities = getCapabilityGroups(user.permissions);

  const accessScope =
    canAccessAll && user.assigned_locations.length === 0
      ? 'All active VMS locations'
      : user.assigned_locations.length > 0
        ? user.assigned_locations.map((l) => l.name).join(', ')
        : 'No locations assigned';

  return (
    <div className="profile-page vms-page-shell">
      <header className="admin-page-header">
        <div>
          <h1 className="admin-page-title">My Profile</h1>
          <p className="admin-page-subtitle">Your VMS staff identity and access scope</p>
        </div>
      </header>

      <div className="profile-tabs">
        <button
          type="button"
          className={`profile-tabs__btn${section === 'profile' ? ' profile-tabs__btn--active' : ''}`}
          onClick={() => setSection('profile')}
        >
          Profile
        </button>
        <button
          type="button"
          className={`profile-tabs__btn${section === 'access' ? ' profile-tabs__btn--active' : ''}`}
          onClick={() => setSection('access')}
        >
          My Access
        </button>
        {canChangePassword && (
          <button
            type="button"
            className={`profile-tabs__btn${section === 'password' ? ' profile-tabs__btn--active' : ''}`}
            onClick={() => setSection('password')}
          >
            Change Password
          </button>
        )}
      </div>

      {section === 'profile' && (
        <div className="profile-card">
          <div className="profile-card__hero">
            <div className="profile-card__avatar-lg">{getInitials(user.display_name, user.email)}</div>
            <div>
              <h2 className="profile-card__name">{displayName}</h2>
              <p className="profile-card__email">{user.email}</p>
              <div className="profile-card__badges">
                <span className="profile-badge">{formatRoleLabel(user.role)}</span>
                {user.is_owner && <span className="profile-badge profile-badge--owner">Owner</span>}
                <span className={`profile-badge${user.is_active ? ' profile-badge--active' : ''}`}>
                  {user.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
            </div>
          </div>

          <dl className="profile-details">
            <div className="profile-details__row">
              <dt>Authentication</dt>
              <dd>{formatAuthProvider(user.auth_provider)}</dd>
            </div>
            <div className="profile-details__row">
              <dt>Identity linked</dt>
              <dd>{user.entra_linked ? 'Yes' : 'No'}</dd>
            </div>
            <div className="profile-details__row">
              <dt>Last login</dt>
              <dd>{formatDateTime(user.last_login_at)}</dd>
            </div>
            <div className="profile-details__row">
              <dt>Locations</dt>
              <dd>{accessScope}</dd>
            </div>
          </dl>

          <p className="profile-readonly-note">
            Profile fields are managed by administrators. Contact your VMS administrator to change role, locations, or account status.
          </p>
        </div>
      )}

      {section === 'password' && canChangePassword && (
        <div className="profile-card">
          <h2 className="profile-card__section-title">Change Password</h2>
          <p className="profile-muted">Update your VMS sign-in password. You will be signed out after a successful change.</p>
          {passwordError && <p className="profile-form__error" role="alert">{passwordError}</p>}
          {passwordSuccess && <p className="profile-form__success" role="status">{passwordSuccess}</p>}
          <form className="profile-password-form" onSubmit={handlePasswordChange}>
            <label className="profile-form__label">
              Current Password
              <input
                type="password"
                className="profile-form__input"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </label>
            <label className="profile-form__label">
              New Password
              <input
                type="password"
                className="profile-form__input"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                autoComplete="new-password"
                minLength={12}
                required
              />
            </label>
            <label className="profile-form__label">
              Confirm New Password
              <input
                type="password"
                className="profile-form__input"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
                minLength={12}
                required
              />
            </label>
            <button type="submit" className="profile-form__submit" disabled={passwordSaving}>
              {passwordSaving ? 'Saving…' : 'Update Password'}
            </button>
          </form>
        </div>
      )}

      {section === 'access' && (
        <div className="profile-card">
          <h2 className="profile-card__section-title">My Access</h2>
          <dl className="profile-details">
            <div className="profile-details__row">
              <dt>Role</dt>
              <dd>{formatRoleLabel(user.role)}</dd>
            </div>
            <div className="profile-details__row">
              <dt>Description</dt>
              <dd>{getRoleDescription(user.role)}</dd>
            </div>
            <div className="profile-details__row">
              <dt>Access scope</dt>
              <dd>{accessScope}</dd>
            </div>
          </dl>

          <h3 className="profile-card__section-title">Capabilities</h3>
          {capabilities.length === 0 ? (
            <p className="profile-muted">No capability groups mapped for your current permissions.</p>
          ) : (
            <ul className="profile-cap-list">
              {capabilities.map((cap) => (
                <li key={cap}>{cap}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
