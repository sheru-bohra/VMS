import { useCallback, useEffect, useState } from 'react';
import { api } from '../../services/api';
import type { AdminRole, Location } from '../../types';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import { formatAuthProvider } from '../../utils/userDisplay';
import '../../styles/admin-pages.css';

interface AdminUserRow {
  id: number;
  email: string;
  display_name: string | null;
  role: AdminRole;
  is_owner: boolean;
  is_active: boolean;
  location_ids: number[];
  assigned_locations: Array<{ id: number; name: string; code: string }>;
  entra_linked: boolean;
  auth_provider?: string | null;
  sso_status?: string;
  access_status?: string;
  last_login_at: string | null;
}

function authMethodLabel(user: AdminUserRow): string {
  if (user.auth_provider === 'vms_native' || user.auth_provider === 'direct') {
    return formatAuthProvider('vms_native');
  }
  if (user.sso_status === 'linked') return 'Microsoft Entra';
  if (user.sso_status === 'identity_issue') return 'Identity issue';
  return 'Not linked';
}

const ROLES: AdminRole[] = ['GLOBAL_ADMIN', 'HEAD_ADMIN', 'SITE_ADMIN', 'SECURITY'];

export function AdministrationUsersPage() {
  const [users, setUsers] = useState<AdminUserRow[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [canManage, setCanManage] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [resetUserId, setResetUserId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [role, setRole] = useState<AdminRole>('SITE_ADMIN');
  const [selectedLocations, setSelectedLocations] = useState<number[]>([]);
  const [temporaryPassword, setTemporaryPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [generatePassword, setGeneratePassword] = useState(true);
  const [forcePasswordChange, setForcePasswordChange] = useState(true);
  const [resetPassword, setResetPassword] = useState('');
  const [resetConfirmPassword, setResetConfirmPassword] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const me = await api.me();
      setCanManage(me.permissions.includes('admins.manage'));
      const [userRows, locs] = await Promise.all([api.adminUsers(), api.locations()]);
      setUsers(userRows);
      setLocations(locs);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load users');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const needsLocations = role === 'SITE_ADMIN' || role === 'SECURITY';

  const toggleLocation = (id: number) => {
    setSelectedLocations((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const handleCreate = async () => {
    setSaving(true);
    setFormError(null);
    try {
      await api.createAdminUser({
        email,
        display_name: displayName,
        role,
        location_ids: needsLocations ? selectedLocations : [],
        is_active: true,
        temporary_password: generatePassword ? undefined : temporaryPassword,
        generate_password: generatePassword,
        force_password_change: forcePasswordChange,
      });
      setFormOpen(false);
      setEmail('');
      setDisplayName('');
      setRole('SITE_ADMIN');
      setSelectedLocations([]);
      setTemporaryPassword('');
      setConfirmPassword('');
      await load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to create user');
    } finally {
      setSaving(false);
    }
  };

  const handleResetPassword = async (user: AdminUserRow) => {
    setSaving(true);
    setFormError(null);
    try {
      await api.resetAdminUserPassword(user.id, {
        temporary_password: resetPassword,
        confirm_password: resetConfirmPassword,
        force_password_change: true,
      });
      setResetUserId(null);
      setResetPassword('');
      setResetConfirmPassword('');
      await load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to reset password');
    } finally {
      setSaving(false);
    }
  };

  const handleDeactivate = async (user: AdminUserRow) => {
    if (user.is_owner) return;
    try {
      await api.deactivateAdminUser(user.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to deactivate user');
    }
  };

  if (loading) return <LoadingState message="Loading users & access…" />;
  if (error) return <ErrorState title="Unable to load users" message={error} action={{ label: 'Retry', onClick: load }} />;

  return (
    <div className="vms-page-shell">
      <div className="admin-page-header">
        <div>
          <h1 className="admin-page-title">Users & Access</h1>
          <p className="admin-page-subtitle">Manage VMS staff accounts, roles, locations, and passwords.</p>
        </div>
        {canManage && (
          <button type="button" className="admin-btn admin-btn--primary" onClick={() => setFormOpen(true)}>
            Add user
          </button>
        )}
      </div>

      {formOpen && canManage && (
        <div className="admin-card" style={{ marginBottom: '1rem' }}>
          <h2 style={{ margin: '0 0 1rem', fontSize: '1rem' }}>Add user</h2>
          {formError && <p className="login-card__error" role="alert">{formError}</p>}
          <div className="admin-form-grid">
            <label>
              Full name
              <input type="text" value={displayName} onChange={(e) => setDisplayName(e.target.value)} required />
            </label>
            <label>
              Corporate email
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </label>
            <label>
              Role
              <select value={role} onChange={(e) => setRole(e.target.value as AdminRole)}>
                {ROLES.map((r) => (
                  <option key={r} value={r}>{r.replace('_', ' ')}</option>
                ))}
              </select>
            </label>
          </div>
          {needsLocations && (
            <div style={{ marginTop: '1rem' }}>
              <p style={{ fontSize: '0.875rem', margin: '0 0 0.5rem' }}>Assigned locations</p>
              <div className="admin-chip-row">
                {locations.map((loc) => (
                  <label key={loc.id} className="admin-chip">
                    <input
                      type="checkbox"
                      checked={selectedLocations.includes(loc.id)}
                      onChange={() => toggleLocation(loc.id)}
                    />
                    {loc.name}
                  </label>
                ))}
              </div>
            </div>
          )}
          <div style={{ marginTop: '1rem' }}>
            <label className="admin-chip">
              <input type="checkbox" checked={generatePassword} onChange={(e) => setGeneratePassword(e.target.checked)} />
              Generate secure temporary password
            </label>
            {!generatePassword && (
              <div className="admin-form-grid" style={{ marginTop: '0.75rem' }}>
                <label>
                  Temporary password
                  <input type="password" value={temporaryPassword} onChange={(e) => setTemporaryPassword(e.target.value)} minLength={12} />
                </label>
                <label>
                  Confirm password
                  <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} minLength={12} />
                </label>
              </div>
            )}
            <label className="admin-chip" style={{ display: 'block', marginTop: '0.75rem' }}>
              <input type="checkbox" checked={forcePasswordChange} onChange={(e) => setForcePasswordChange(e.target.checked)} />
              Require password change on first login
            </label>
          </div>
          <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem' }}>
            <button type="button" className="admin-btn admin-btn--primary" disabled={saving} onClick={handleCreate}>
              Create user
            </button>
            <button type="button" className="admin-btn" onClick={() => setFormOpen(false)}>Cancel</button>
          </div>
        </div>
      )}

      {resetUserId !== null && canManage && (
        <div className="admin-card" style={{ marginBottom: '1rem' }}>
          <h2 style={{ margin: '0 0 1rem', fontSize: '1rem' }}>Reset password</h2>
          {formError && <p className="login-card__error" role="alert">{formError}</p>}
          <div className="admin-form-grid">
            <label>
              New temporary password
              <input type="password" value={resetPassword} onChange={(e) => setResetPassword(e.target.value)} minLength={12} />
            </label>
            <label>
              Confirm temporary password
              <input type="password" value={resetConfirmPassword} onChange={(e) => setResetConfirmPassword(e.target.value)} minLength={12} />
            </label>
          </div>
          <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem' }}>
            <button
              type="button"
              className="admin-btn admin-btn--primary"
              disabled={saving}
              onClick={() => {
                const target = users.find((u) => u.id === resetUserId);
                if (target) handleResetPassword(target);
              }}
            >
              Reset password
            </button>
            <button type="button" className="admin-btn" onClick={() => setResetUserId(null)}>Cancel</button>
          </div>
        </div>
      )}

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>User</th>
              <th>Email</th>
              <th>Role</th>
              <th>Location(s)</th>
              <th>Authentication</th>
              <th>Status</th>
              <th>Last Login</th>
              {canManage && <th>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <td>{user.display_name ?? '—'}</td>
                <td>{user.email}</td>
                <td>
                  {user.role.replace('_', ' ')}
                  {user.is_owner && <span style={{ display: 'block', fontSize: '0.75rem', color: 'var(--color-slate-500)' }}>Owner</span>}
                </td>
                <td>{user.assigned_locations.map((l) => l.name).join(', ') || '—'}</td>
                <td>{authMethodLabel(user)}</td>
                <td>{user.access_status === 'disabled' ? 'Inactive' : 'Active'}</td>
                <td>{user.last_login_at ? new Date(user.last_login_at).toLocaleString() : '—'}</td>
                {canManage && (
                  <td style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                    {!user.is_owner && (
                      <button type="button" className="admin-btn admin-btn--sm" onClick={() => setResetUserId(user.id)}>
                        Reset password
                      </button>
                    )}
                    {!user.is_owner && user.is_active && (
                      <button type="button" className="admin-btn admin-btn--sm" onClick={() => handleDeactivate(user)}>
                        Deactivate
                      </button>
                    )}
                    {user.is_owner && <span style={{ fontSize: '0.75rem', color: 'var(--color-slate-500)' }}>Protected</span>}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
