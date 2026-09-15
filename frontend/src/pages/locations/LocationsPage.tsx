import { useCallback, useEffect, useRef, useState } from 'react';
import QRCode from 'qrcode';
import { api } from '../../services/api';
import type { AdminRole, Location, LocationRetireSummary, LocationStaffMember } from '../../types';
import { useAuth } from '../../hooks/useAuth';
import { hasPermission } from '../../utils/permissions';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import '../../styles/admin-pages.css';
import '../../styles/locations-page.css';

const SITE_STAFF_ROLES: AdminRole[] = ['SITE_ADMIN', 'SECURITY'];

const TIMEZONE_OPTIONS = [
  'Asia/Kolkata',
  'Asia/Dubai',
  'Asia/Singapore',
  'Europe/London',
  'Europe/Berlin',
  'America/New_York',
  'America/Los_Angeles',
  'UTC',
];

function SiteAdminIcon() {
  return (
    <svg className="loc-staff-badge__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M19 8v6M22 11h-6" />
    </svg>
  );
}

function SecurityIcon() {
  return (
    <svg className="loc-staff-badge__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

function NoStaffIcon() {
  return (
    <svg className="loc-staff-badge__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <line x1="17" y1="8" x2="23" y2="14" />
      <line x1="23" y1="8" x2="17" y2="14" />
    </svg>
  );
}

function formatSiteAdminLabel(count: number): string {
  return count === 1 ? '1 Site Admin' : `${count} Site Admins`;
}

function formatSecurityLabel(count: number): string {
  return count === 1 ? '1 Security' : `${count} Security`;
}

function SiteStaffBadges({ location }: { location: Location }) {
  const admins = location.site_admin_count ?? 0;
  const security = location.security_count ?? 0;
  const total = location.site_staff_count ?? 0;

  if (total === 0) {
    return (
      <span className="loc-staff-badge loc-staff-badge--empty">
        <NoStaffIcon />
        No staff assigned
      </span>
    );
  }

  return (
    <div className="loc-staff-badges">
      {admins > 0 && (
        <span
          className="loc-staff-badge loc-staff-badge--site-admin"
          title={`${formatSiteAdminLabel(admins)} assigned to this location`}
        >
          <SiteAdminIcon />
          {formatSiteAdminLabel(admins)}
        </span>
      )}
      {security > 0 && (
        <span
          className="loc-staff-badge loc-staff-badge--security"
          title={`${formatSecurityLabel(security)} assigned to this location`}
        >
          <SecurityIcon />
          {formatSecurityLabel(security)}
        </span>
      )}
    </div>
  );
}

function QrModal({
  location,
  onClose,
}: {
  location: Location;
  onClose: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const url = location.registration_url ?? '';

  useEffect(() => {
    if (canvasRef.current && url) {
      QRCode.toCanvas(canvasRef.current, url, { width: 240, margin: 2 });
    }
  }, [url]);

  const copyLink = () => {
    if (url) navigator.clipboard.writeText(url);
  };

  const downloadPng = () => {
    if (!canvasRef.current) return;
    const link = document.createElement('a');
    link.download = `${location.code}-registration-qr.png`;
    link.href = canvasRef.current.toDataURL('image/png');
    link.click();
  };

  return (
    <div className="admin-qr-modal" onClick={onClose}>
      <div className="admin-qr-content" onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: '0 0 0.5rem', fontSize: '1rem' }}>{location.name}</h3>
        <p style={{ fontSize: '0.8125rem', color: 'var(--color-slate-500)', margin: '0 0 1rem' }}>
          Reception registration QR
        </p>
        {url ? (
          <>
            <canvas ref={canvasRef} style={{ margin: '0 auto' }} />
            <p style={{ fontSize: '0.75rem', color: 'var(--color-slate-500)', margin: '0.75rem 0', wordBreak: 'break-all' }}>
              {url}
            </p>
            <div className="admin-qr-actions">
              <button type="button" className="admin-btn admin-btn--primary" onClick={downloadPng}>Download QR PNG</button>
              <button type="button" className="admin-btn" onClick={copyLink}>Copy Registration Link</button>
              <button type="button" className="admin-btn" onClick={onClose}>Close</button>
            </div>
          </>
        ) : (
          <p>Registration link not available for this location.</p>
        )}
      </div>
    </div>
  );
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2M19 6l-1 14a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1L5 6" />
      <path d="M10 11v6M14 11v6" />
    </svg>
  );
}

function DeleteLocationModal({
  location,
  onClose,
  onDeleted,
}: {
  location: Location;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const [summary, setSummary] = useState<LocationRetireSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [confirmText, setConfirmText] = useState('');
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCloseRef.current();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.body.style.overflow = prevOverflow;
      document.removeEventListener('keydown', onKeyDown);
    };
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.locationRetireSummary(location.id)
      .then(setSummary)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load delete summary'))
      .finally(() => setLoading(false));
  }, [location.id]);

  const confirmReady = confirmText.trim() === 'Delete Location';

  const handleDelete = async () => {
    if (!confirmReady || saving) return;
    setSaving(true);
    setError(null);
    try {
      await api.retireLocation(location.id, reason.trim() || undefined);
      onDeleted();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete location');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="admin-qr-modal" onClick={onClose}>
      <div
        ref={dialogRef}
        className="loc-add-modal loc-delete-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="loc-delete-title"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="loc-add-modal__header">
          <div>
            <h2 id="loc-delete-title">Delete Location?</h2>
            <p className="loc-add-modal__subtitle">
              {location.name} · {location.code}
            </p>
          </div>
          <button type="button" className="loc-add-modal__close" onClick={onClose} aria-label="Close">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </header>

        <div className="loc-add-modal__body">
          <p className="loc-delete-warning">
            Deleting this location will remove it from active VMS operations and disable new registrations.
            Historical visitor, audit, and reporting records will be retained.
          </p>

          {loading && <p>Loading dependency summary…</p>}
          {summary && (
            <ul className="loc-delete-summary">
              <li>Assigned staff: <strong>{summary.assigned_staff}</strong></li>
              <li>Future visits: <strong>{summary.future_visits}</strong></li>
              <li>Visitors currently onsite: <strong>{summary.onsite_visitors}</strong></li>
              <li>Pending approvals: <strong>{summary.pending_approvals}</strong></li>
              <li>Active emergency: <strong>{summary.active_emergency ? 'Yes' : 'No'}</strong></li>
            </ul>
          )}

          <div className="loc-field" style={{ marginTop: '1rem' }}>
            <label htmlFor="loc-delete-reason">Reason for removal (optional)</label>
            <input
              id="loc-delete-reason"
              className="loc-input"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Office closed, location merged…"
            />
          </div>
          <div className="loc-field">
            <label htmlFor="loc-delete-confirm">
              Type <strong>Delete Location</strong> to confirm
            </label>
            <input
              id="loc-delete-confirm"
              className="loc-input"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              placeholder="Delete Location"
            />
          </div>
          {error && <p className="loc-form-error" style={{ marginTop: '0.75rem' }}>{error}</p>}
        </div>

        <footer className="loc-add-modal__footer">
          <button type="button" className="admin-btn admin-btn--secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="admin-btn admin-btn--danger"
            onClick={handleDelete}
            disabled={!confirmReady || saving || (summary && !summary.can_retire)}
          >
            {saving ? 'Deleting…' : 'Delete Location'}
          </button>
        </footer>
      </div>
    </div>
  );
}

function AddLocationModal({
  onClose,
  onCreated,
  returnFocusRef,
}: {
  onClose: () => void;
  onCreated: () => void;
  returnFocusRef?: React.RefObject<HTMLButtonElement | null>;
}) {
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [timezone, setTimezone] = useState('Asia/Kolkata');
  const [registrationEnabled, setRegistrationEnabled] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const firstInput = dialogRef.current?.querySelector<HTMLInputElement>('input');
    firstInput?.focus();

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCloseRef.current();
    };
    document.addEventListener('keydown', onKeyDown);

    return () => {
      document.body.style.overflow = prevOverflow;
      document.removeEventListener('keydown', onKeyDown);
      returnFocusRef?.current?.focus();
    };
  }, [returnFocusRef]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.createLocation({
        name: name.trim(),
        code: code.trim(),
        timezone: timezone.trim(),
        registration_enabled: registrationEnabled,
      });
      onCreated();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create location');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="admin-qr-modal" onClick={onClose}>
      <div
        ref={dialogRef}
        className="loc-add-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="loc-add-title"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="loc-add-modal__header">
          <div>
            <h2 id="loc-add-title">Add Location</h2>
            <p className="loc-add-modal__subtitle">Create a new VMS office location.</p>
          </div>
          <button type="button" className="loc-add-modal__close" onClick={onClose} aria-label="Close">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </header>

        <form onSubmit={handleSubmit}>
          <div className="loc-add-modal__body">
            <div className="loc-add-modal__grid">
              <div className="loc-field">
                <label htmlFor="loc-name">
                  Location Name <span className="loc-required">*</span>
                </label>
                <input
                  id="loc-name"
                  className="loc-input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  placeholder="Bangalore Office"
                />
              </div>
              <div className="loc-field">
                <label htmlFor="loc-code">
                  Location Code <span className="loc-required">*</span>
                </label>
                <input
                  id="loc-code"
                  className="loc-input"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  required
                  placeholder="BLR"
                />
              </div>
              <div className="loc-field">
                <label htmlFor="loc-timezone">
                  Timezone <span className="loc-required">*</span>
                </label>
                <select
                  id="loc-timezone"
                  className="loc-select"
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  required
                >
                  {TIMEZONE_OPTIONS.map((tz) => (
                    <option key={tz} value={tz}>{tz}</option>
                  ))}
                </select>
              </div>
              <div className="loc-field loc-field--registration">
                <span className="loc-field__static-label">Public Registration</span>
                <div className="loc-registration-card">
                  <div className="loc-registration-card__text">
                    <p>Allow visitors to use this location&apos;s self-registration QR.</p>
                  </div>
                  <label className="loc-toggle" aria-label="Public registration enabled">
                    <input
                      type="checkbox"
                      checked={registrationEnabled}
                      onChange={(e) => setRegistrationEnabled(e.target.checked)}
                    />
                    <span className="loc-toggle__track" />
                  </label>
                </div>
              </div>
            </div>
          </div>

          {error && <p className="loc-form-error">{error}</p>}

          <footer className="loc-add-modal__footer">
            <button type="button" className="admin-btn admin-btn--secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="admin-btn admin-btn--primary" disabled={saving}>
              {saving ? 'Creating…' : 'Create Location'}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}

function ManageAccessModal({
  location,
  onClose,
  onUpdated,
}: {
  location: Location;
  onClose: () => void;
  onUpdated: () => void;
}) {
  const [staff, setStaff] = useState<LocationStaffMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [role, setRole] = useState<AdminRole>('SITE_ADMIN');
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [removeTarget, setRemoveTarget] = useState<LocationStaffMember | null>(null);

  const loadStaff = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await api.locationStaff(location.id);
      setStaff(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load staff');
    } finally {
      setLoading(false);
    }
  }, [location.id]);

  useEffect(() => {
    loadStaff();
  }, [loadStaff]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setFormError(null);
    try {
      await api.addLocationStaff(location.id, {
        email: email.trim(),
        display_name: displayName.trim(),
        role,
      });
      setEmail('');
      setDisplayName('');
      setRole('SITE_ADMIN');
      setAddOpen(false);
      await loadStaff();
      onUpdated();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to add staff');
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async () => {
    if (!removeTarget) return;
    setSaving(true);
    try {
      await api.removeLocationStaff(location.id, removeTarget.user_id);
      setRemoveTarget(null);
      await loadStaff();
      onUpdated();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to remove assignment');
    } finally {
      setSaving(false);
    }
  };

  const siteAdmins = staff.filter((s) => s.role === 'SITE_ADMIN');
  const securityStaff = staff.filter((s) => s.role === 'SECURITY');

  return (
    <div className="admin-qr-modal" onClick={onClose}>
      <div
        className="admin-qr-content"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: '42rem', width: '100%' }}
      >
        <h3 style={{ margin: '0 0 0.25rem', fontSize: '1rem' }}>Location Access</h3>
        <p style={{ fontSize: '0.8125rem', color: 'var(--color-slate-500)', margin: '0 0 1rem' }}>
          {location.name} · {location.code}
        </p>

        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', fontSize: '0.8125rem' }}>
          <span>Site Admins: {siteAdmins.length}</span>
          <span>Security: {securityStaff.length}</span>
        </div>

        {loading && <p>Loading assigned staff…</p>}
        {error && <p className="admin-form-error">{error}</p>}

        {!loading && !error && (
          <>
            <div className="admin-table-wrap" style={{ marginBottom: '1rem' }}>
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {staff.length === 0 && (
                    <tr>
                      <td colSpan={5} style={{ color: 'var(--color-slate-500)' }}>No site staff assigned</td>
                    </tr>
                  )}
                  {staff.map((member) => (
                    <tr key={member.user_id}>
                      <td>{member.display_name || '—'}</td>
                      <td>{member.email}</td>
                      <td>{member.role}</td>
                      <td>{member.is_active ? 'Active' : 'Disabled'}</td>
                      <td>
                        <button
                          type="button"
                          className="admin-btn admin-btn--sm"
                          onClick={() => setRemoveTarget(member)}
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {!addOpen && (
              <button type="button" className="admin-btn admin-btn--primary" onClick={() => setAddOpen(true)}>
                + Add Site User
              </button>
            )}

            {addOpen && (
              <form onSubmit={handleAdd} className="admin-form-grid" style={{ marginTop: '1rem', borderTop: '1px solid var(--color-slate-200)', paddingTop: '1rem' }}>
                <h4 style={{ margin: '0 0 0.75rem', fontSize: '0.875rem', gridColumn: '1 / -1' }}>Add Site User</h4>
                <label>
                  Corporate Email *
                  <input value={email} onChange={(e) => setEmail(e.target.value)} required type="email" />
                </label>
                <label>
                  Display Name *
                  <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} required />
                </label>
                <label>
                  Role *
                  <select value={role} onChange={(e) => setRole(e.target.value as AdminRole)}>
                    {SITE_STAFF_ROLES.map((r) => (
                      <option key={r} value={r}>{r}</option>
                    ))}
                  </select>
                </label>
                {formError && <p style={{ color: 'var(--color-danger)', fontSize: '0.875rem', gridColumn: '1 / -1' }}>{formError}</p>}
                <div className="admin-qr-actions">
                  <button type="submit" className="admin-btn admin-btn--primary" disabled={saving}>
                    {saving ? 'Saving…' : 'Assign User'}
                  </button>
                  <button type="button" className="admin-btn" onClick={() => setAddOpen(false)}>Cancel</button>
                </div>
              </form>
            )}
          </>
        )}

        {removeTarget && (
          <div style={{ marginTop: '1rem', padding: '1rem', background: 'var(--color-slate-50)', borderRadius: '6px' }}>
            <p style={{ margin: '0 0 0.5rem', fontWeight: 600 }}>Remove access to {location.name}?</p>
            <p style={{ margin: '0 0 0.25rem', fontSize: '0.8125rem' }}>{removeTarget.display_name || removeTarget.email}</p>
            <p style={{ margin: '0 0 0.75rem', fontSize: '0.8125rem', color: 'var(--color-slate-500)' }}>
              Role: {removeTarget.role}. This removes only the {location.name} assignment.
            </p>
            <div className="admin-qr-actions">
              <button type="button" className="admin-btn admin-btn--primary" onClick={handleRemove} disabled={saving}>
                Remove Access
              </button>
              <button type="button" className="admin-btn" onClick={() => setRemoveTarget(null)}>Cancel</button>
            </div>
          </div>
        )}

        <div className="admin-qr-actions" style={{ marginTop: '1rem' }}>
          <button type="button" className="admin-btn" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

export function LocationsPage() {
  const { user } = useAuth();
  const canManage = user ? hasPermission(user.permissions, 'locations.manage') : false;
  const [locations, setLocations] = useState<Location[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [qrLocation, setQrLocation] = useState<Location | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [deleteLocation, setDeleteLocation] = useState<Location | null>(null);
  const [accessLocation, setAccessLocation] = useState<Location | null>(null);
  const addButtonRef = useRef<HTMLButtonElement>(null);

  const loadLocations = useCallback(() => {
    setLoading(true);
    setError(null);
    api.locations()
      .then(setLocations)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadLocations();
  }, [loadLocations]);

  if (loading) return <LoadingState message="Loading locations…" />;
  if (error) return <ErrorState title="Unable to load locations" message={error} action={{ label: 'Retry', onClick: loadLocations }} />;

  return (
    <div>
      <header style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>Locations</h1>
          <p style={{ fontSize: '0.875rem', color: 'var(--color-slate-500)', margin: '0.25rem 0 0' }}>
            Site locations, registration and location-level access
          </p>
        </div>
        {canManage && (
          <button
            ref={addButtonRef}
            type="button"
            className="admin-btn admin-btn--primary"
            onClick={() => setAddOpen(true)}
          >
            + Add Location
          </button>
        )}
      </header>

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Code</th>
              <th>Timezone</th>
              <th>Registration</th>
              <th>Site Staff</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {locations.map((loc) => (
              <tr key={loc.id} style={{ cursor: 'default' }}>
                <td>
                  {loc.name}
                  {loc.is_development_seed && (
                    <span style={{ fontSize: '0.75rem', color: 'var(--color-slate-400)' }}> (dev seed)</span>
                  )}
                </td>
                <td>{loc.code}</td>
                <td>{loc.timezone || '—'}</td>
                <td>{loc.registration_enabled ? 'Enabled' : 'Disabled'}</td>
                <td>
                  <SiteStaffBadges location={loc} />
                </td>
                <td className="loc-actions-cell">
                  {canManage && (
                    <button type="button" className="admin-btn" onClick={() => setAccessLocation(loc)}>
                      Manage Access
                    </button>
                  )}
                  {loc.registration_url && (
                    <button type="button" className="admin-btn" onClick={() => setQrLocation(loc)}>
                      View QR
                    </button>
                  )}
                  {canManage && (
                    <button
                      type="button"
                      className="admin-btn admin-btn--danger-outline"
                      onClick={() => setDeleteLocation(loc)}
                    >
                      <TrashIcon />
                      Delete
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {qrLocation && <QrModal location={qrLocation} onClose={() => setQrLocation(null)} />}
      {addOpen && (
        <AddLocationModal
          onClose={() => setAddOpen(false)}
          onCreated={loadLocations}
          returnFocusRef={addButtonRef}
        />
      )}
      {deleteLocation && (
        <DeleteLocationModal
          location={deleteLocation}
          onClose={() => setDeleteLocation(null)}
          onDeleted={loadLocations}
        />
      )}
      {accessLocation && (
        <ManageAccessModal
          location={accessLocation}
          onClose={() => setAccessLocation(null)}
          onUpdated={loadLocations}
        />
      )}
    </div>
  );
}
