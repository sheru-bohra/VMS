import { useCallback, useEffect, useState } from 'react';
import { api } from '../../services/api';
import type { WatchlistItem } from '../../types';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import { useAuth } from '../../hooks/useAuth';
import { hasPermission } from '../../utils/permissions';
import '../../styles/admin-pages.css';

const REASON_OPTIONS = [
  { code: 'PREVIOUS_SECURITY_INCIDENT', label: 'Previous security incident' },
  { code: 'ACCESS_RESTRICTED', label: 'Access restricted' },
  { code: 'REPEATED_POLICY_VIOLATION', label: 'Repeated policy violation' },
  { code: 'INTERNAL_SECURITY_NOTICE', label: 'Internal security notice' },
  { code: 'OTHER', label: 'Other' },
];

export function WatchlistPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [scopeFilter, setScopeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('ACTIVE');
  const [selected, setSelected] = useState<WatchlistItem | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [form, setForm] = useState({
    scope_type: 'GLOBAL',
    location_id: '',
    full_name: '',
    mobile: '',
    email: '',
    company: '',
    reason_code: 'ACCESS_RESTRICTED',
    reason_text: '',
    action_level: 'REVIEW',
    valid_from: new Date().toISOString().slice(0, 16),
    valid_until: '',
  });

  const canCreateGlobal = user && hasPermission(user.permissions, 'watchlist.create');
  const canCreateLocation = user && hasPermission(user.permissions, 'watchlist.create_location');
  const canCreate = canCreateGlobal || canCreateLocation;
  const canDeactivate = user && hasPermission(user.permissions, 'watchlist.deactivate');

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await api.watchlist({
        search: search || undefined,
        scope: scopeFilter || undefined,
        status: statusFilter || undefined,
        limit: 50,
      });
      setItems(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load watchlist');
    } finally {
      setLoading(false);
    }
  }, [search, scopeFilter, statusFilter]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  const openDetail = async (item: WatchlistItem) => {
    try {
      const detail = await api.watchlistDetail(item.id);
      setSelected(detail);
    } catch {
      setSelected(item);
    }
  };

  const handleDeactivate = async () => {
    if (!selected) return;
    setActionLoading(true);
    try {
      const updated = await api.deactivateWatchlistEntry(selected.id);
      setSelected(updated);
      setItems((prev) => prev.map((i) => (i.id === updated.id ? updated : i)));
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Unable to deactivate');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCreate = async () => {
    setFormError(null);
    if (!form.full_name.trim()) {
      setFormError('Name is required.');
      return;
    }
    if (form.reason_code === 'OTHER' && !form.reason_text.trim()) {
      setFormError('Reason text is required for Other.');
      return;
    }
    const scope = canCreateGlobal && form.scope_type === 'GLOBAL' ? 'GLOBAL' : 'LOCATION';
    if (scope === 'LOCATION' && !form.location_id) {
      setFormError('Location is required for location-scoped entries.');
      return;
    }
    setActionLoading(true);
    try {
      const payload = {
        scope_type: scope,
        location_id: scope === 'LOCATION' ? Number(form.location_id) : null,
        full_name: form.full_name.trim(),
        mobile: form.mobile || null,
        email: form.email || null,
        company: form.company || null,
        reason_code: form.reason_code,
        reason_text: form.reason_text || null,
        action_level: form.action_level,
        valid_from: new Date(form.valid_from).toISOString(),
        valid_until: form.valid_until ? new Date(form.valid_until).toISOString() : null,
      };
      const created = await api.createWatchlistEntry(payload);
      setShowCreate(false);
      setItems((prev) => [created, ...prev]);
      setSelected(created);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Unable to create entry');
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="vms-page-shell">
      <header style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>Watchlist</h1>
          <p style={{ fontSize: '0.875rem', color: 'var(--color-slate-500)', margin: '0.25rem 0 0' }}>Security watchlist administration</p>
        </div>
        {canCreate && (
          <button type="button" className="admin-btn admin-btn--primary" onClick={() => { setShowCreate(true); setFormError(null); }}>
            Add Entry
          </button>
        )}
      </header>

      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
        <input
          type="search"
          placeholder="Search name / mobile / email / company"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ minWidth: '220px' }}
        />
        <select value={scopeFilter} onChange={(e) => setScopeFilter(e.target.value)}>
          <option value="">All scopes</option>
          <option value="GLOBAL">Global</option>
          <option value="LOCATION">Location</option>
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          <option value="ACTIVE">Active</option>
          <option value="INACTIVE">Inactive</option>
        </select>
        <button type="button" className="admin-btn" onClick={() => { setLoading(true); load(); }}>Refresh</button>
      </div>

      {loading && <LoadingState message="Loading watchlist…" />}
      {error && <ErrorState title="Unable to load" message={error} action={{ label: 'Retry', onClick: () => { setLoading(true); load(); } }} />}

      {!loading && !error && items.length === 0 && (
        <div className="empty-state">
          <h3 className="empty-state__title">No watchlist entries</h3>
          <p className="empty-state__message">Matching entries will appear here.</p>
        </div>
      )}

      {!loading && !error && items.length > 0 && (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Person</th>
                <th className="col-hide-mobile">Company</th>
                <th>Scope</th>
                <th>Action</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} onClick={() => openDetail(item)}>
                  <td>{item.full_name}</td>
                  <td className="col-hide-mobile">{item.company ?? '—'}</td>
                  <td>{item.scope_type === 'GLOBAL' ? 'Global' : item.location_name ?? 'Location'}</td>
                  <td>{item.action_level}</td>
                  <td>{item.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <div className="admin-detail-overlay" onClick={() => setSelected(null)}>
          <div className="admin-detail-panel" onClick={(e) => e.stopPropagation()}>
            <button type="button" className="admin-btn" onClick={() => setSelected(null)} style={{ marginBottom: '1rem' }}>Close</button>
            <h2>{selected.full_name}</h2>
            <div className="admin-detail-row"><div className="admin-detail-label">Mobile</div><div>{selected.mobile ?? '—'}</div></div>
            <div className="admin-detail-row"><div className="admin-detail-label">Email</div><div>{selected.email ?? '—'}</div></div>
            <div className="admin-detail-row"><div className="admin-detail-label">Company</div><div>{selected.company ?? '—'}</div></div>
            <div className="admin-detail-row"><div className="admin-detail-label">Scope</div><div>{selected.scope_type}</div></div>
            {selected.location_name && (
              <div className="admin-detail-row"><div className="admin-detail-label">Location</div><div>{selected.location_name}</div></div>
            )}
            <div className="admin-detail-row"><div className="admin-detail-label">Reason</div><div>{selected.reason_code}{selected.reason_text ? `: ${selected.reason_text}` : ''}</div></div>
            <div className="admin-detail-row"><div className="admin-detail-label">Action Level</div><div>{selected.action_level}</div></div>
            <div className="admin-detail-row"><div className="admin-detail-label">Valid From</div><div>{selected.valid_from ? new Date(selected.valid_from).toLocaleString() : '—'}</div></div>
            <div className="admin-detail-row"><div className="admin-detail-label">Valid Until</div><div>{selected.valid_until ? new Date(selected.valid_until).toLocaleString() : '—'}</div></div>
            <div className="admin-detail-row"><div className="admin-detail-label">Status</div><div>{selected.status}</div></div>
            {canDeactivate && selected.status === 'ACTIVE' && (
              <div style={{ marginTop: '1rem' }}>
                {formError && <p style={{ color: 'var(--color-danger)', fontSize: '0.8125rem' }}>{formError}</p>}
                <button type="button" className="admin-btn admin-btn--danger" disabled={actionLoading} onClick={handleDeactivate}>
                  Deactivate
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {showCreate && (
        <div className="admin-detail-overlay" onClick={() => setShowCreate(false)}>
          <div className="admin-detail-panel" onClick={(e) => e.stopPropagation()}>
            <button type="button" className="admin-btn" onClick={() => setShowCreate(false)} style={{ marginBottom: '1rem' }}>Close</button>
            <h2>New Watchlist Entry</h2>
            {canCreateGlobal && (
              <label style={{ display: 'block', marginBottom: '0.75rem' }}>
                Scope
                <select value={form.scope_type} onChange={(e) => setForm((f) => ({ ...f, scope_type: e.target.value }))} style={{ width: '100%', marginTop: '0.25rem' }}>
                  <option value="GLOBAL">Global</option>
                  <option value="LOCATION">Location</option>
                </select>
              </label>
            )}
            {(form.scope_type === 'LOCATION' || !canCreateGlobal) && (
              <label style={{ display: 'block', marginBottom: '0.75rem' }}>
                Location
                <select value={form.location_id} onChange={(e) => setForm((f) => ({ ...f, location_id: e.target.value }))} style={{ width: '100%', marginTop: '0.25rem' }}>
                  <option value="">Select location</option>
                  {(user?.assigned_locations ?? []).map((loc) => (
                    <option key={loc.id} value={loc.id}>{loc.name}</option>
                  ))}
                </select>
              </label>
            )}
            <label style={{ display: 'block', marginBottom: '0.75rem' }}>
              Full name *
              <input value={form.full_name} onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))} style={{ width: '100%', marginTop: '0.25rem' }} />
            </label>
            <label style={{ display: 'block', marginBottom: '0.75rem' }}>
              Mobile
              <input value={form.mobile} onChange={(e) => setForm((f) => ({ ...f, mobile: e.target.value }))} style={{ width: '100%', marginTop: '0.25rem' }} />
            </label>
            <label style={{ display: 'block', marginBottom: '0.75rem' }}>
              Email
              <input value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} style={{ width: '100%', marginTop: '0.25rem' }} />
            </label>
            <label style={{ display: 'block', marginBottom: '0.75rem' }}>
              Company
              <input value={form.company} onChange={(e) => setForm((f) => ({ ...f, company: e.target.value }))} style={{ width: '100%', marginTop: '0.25rem' }} />
            </label>
            <label style={{ display: 'block', marginBottom: '0.75rem' }}>
              Reason *
              <select value={form.reason_code} onChange={(e) => setForm((f) => ({ ...f, reason_code: e.target.value }))} style={{ width: '100%', marginTop: '0.25rem' }}>
                {REASON_OPTIONS.map((r) => (
                  <option key={r.code} value={r.code}>{r.label}</option>
                ))}
              </select>
            </label>
            {form.reason_code === 'OTHER' && (
              <label style={{ display: 'block', marginBottom: '0.75rem' }}>
                Reason details *
                <textarea value={form.reason_text} onChange={(e) => setForm((f) => ({ ...f, reason_text: e.target.value }))} rows={2} style={{ width: '100%', marginTop: '0.25rem' }} />
              </label>
            )}
            <label style={{ display: 'block', marginBottom: '0.75rem' }}>
              Action level *
              <select value={form.action_level} onChange={(e) => setForm((f) => ({ ...f, action_level: e.target.value }))} style={{ width: '100%', marginTop: '0.25rem' }}>
                <option value="REVIEW">Review</option>
                <option value="BLOCK">Block</option>
              </select>
            </label>
            <label style={{ display: 'block', marginBottom: '0.75rem' }}>
              Valid from *
              <input type="datetime-local" value={form.valid_from} onChange={(e) => setForm((f) => ({ ...f, valid_from: e.target.value }))} style={{ width: '100%', marginTop: '0.25rem' }} />
            </label>
            <label style={{ display: 'block', marginBottom: '0.75rem' }}>
              Valid until
              <input type="datetime-local" value={form.valid_until} onChange={(e) => setForm((f) => ({ ...f, valid_until: e.target.value }))} style={{ width: '100%', marginTop: '0.25rem' }} />
            </label>
            {formError && <p style={{ color: 'var(--color-danger)', fontSize: '0.8125rem', margin: '0 0 0.5rem' }}>{formError}</p>}
            <button type="button" className="admin-btn admin-btn--primary" disabled={actionLoading} onClick={handleCreate}>
              Create Entry
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
