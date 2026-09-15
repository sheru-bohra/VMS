import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiClientError } from '../../services/api';
import type { OperationalVisit } from '../../types';
import { formatDuration } from '../../types';
import { useAuth } from '../../hooks/useAuth';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { useOperationalLocations } from '../../hooks/useOperationalLocations';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import { Toast } from '../../components/admin/Toast';
import { useOperationalPolling } from '../../hooks/useOperationalPolling';
import { triggerOperationalRefresh } from '../../utils/operationalRefreshEvents';
import '../../styles/admin-pages.css';
import '../../styles/registration.css';

const STATUS_OPTIONS = [
  { id: 'ALL', label: 'All statuses' },
  { id: 'APPROVED', label: 'Approved' },
  { id: 'ARRIVED', label: 'Arrived' },
  { id: 'ONSITE', label: 'Onsite' },
  { id: 'CHECKED_OUT', label: 'Checked out' },
];

function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hr ago`;
  return new Date(iso).toLocaleString();
}

function DetailPanel({
  item,
  onClose,
  onUpdated,
  onToast,
  onRefresh,
}: {
  item: OperationalVisit;
  onClose: () => void;
  onUpdated: () => void;
  onToast: (msg: string, type?: 'success' | 'error') => void;
  onRefresh: () => void;
}) {
  const [arriveOpen, setArriveOpen] = useState(false);
  const [checkInOpen, setCheckInOpen] = useState(false);
  const [acting, setActing] = useState(false);

  const handleArrive = async () => {
    setActing(true);
    try {
      await api.arriveVisit(item.id);
      onToast('Visitor marked as arrived.');
      triggerOperationalRefresh();
      setArriveOpen(false);
      onUpdated();
      onClose();
    } catch (err) {
      if (err instanceof ApiClientError && err.status === 409) {
        onToast(err.message, 'error');
        onRefresh();
      } else {
        onToast(err instanceof Error ? err.message : 'Arrival failed.', 'error');
      }
    } finally {
      setActing(false);
    }
  };

  const handleCheckIn = async () => {
    setActing(true);
    try {
      await api.checkInVisit(item.id);
      onToast('Visitor checked in successfully.');
      triggerOperationalRefresh();
      setCheckInOpen(false);
      onUpdated();
      onClose();
    } catch (err) {
      if (err instanceof ApiClientError && err.status === 409) {
        onToast(err.message, 'error');
        onRefresh();
      } else {
        onToast(err instanceof Error ? err.message : 'Check-in failed.', 'error');
      }
    } finally {
      setActing(false);
    }
  };

  const lastApproval = item.approval_history?.length
    ? item.approval_history[item.approval_history.length - 1]
    : null;

  return (
    <div className="admin-detail-overlay" onClick={onClose}>
      <div className="admin-detail-panel" onClick={(e) => e.stopPropagation()} role="dialog">
        <button type="button" className="admin-btn" onClick={onClose} style={{ marginBottom: '1rem' }}>Close</button>
        <h2>Visitor Details</h2>
        <p style={{ fontSize: '1.0625rem', fontWeight: 600, margin: '0 0 0.25rem' }}>{item.visitor_name}</p>
        <p style={{ fontSize: '0.875rem', color: 'var(--color-slate-500)', margin: '0 0 1rem' }}>
          {item.visitor_type ?? 'Visitor'}
          {item.company ? ` · ${item.company}` : ''}
        </p>

        <div className="admin-detail-row">
          <div className="admin-detail-label">Host</div>
          <div className="admin-detail-value">{item.host_name ?? '—'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Site</div>
          <div className="admin-detail-value">{item.site_name}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Purpose</div>
          <div className="admin-detail-value">{item.purpose ?? '—'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Expected stay</div>
          <div className="admin-detail-value">{formatDuration(item.expected_duration_minutes)}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Mobile</div>
          <div className="admin-detail-value">{item.visitor_mobile ?? '—'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Email</div>
          <div className="admin-detail-value">{item.visitor_email ?? '—'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Policy</div>
          <div className="admin-detail-value">{item.policy_accepted ? 'Accepted' : '—'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Registration</div>
          <div className="admin-detail-value">{item.registration_reference ?? '—'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Status</div>
          <div className="admin-detail-value"><StatusBadge status={item.status} /></div>
        </div>
        {item.is_walk_in && item.status === 'APPROVED' && (
          <p style={{ fontSize: '0.8125rem', color: 'var(--color-slate-500)', marginTop: '0.5rem' }}>
            Approved walk-in for today
          </p>
        )}
        {lastApproval && (
          <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--color-slate-200)' }}>
            <div className="admin-detail-label">Approval</div>
            <p style={{ fontSize: '0.875rem', margin: '0.25rem 0 0' }}>
              {lastApproval.decision} by {lastApproval.actor_email ?? '—'}
            </p>
          </div>
        )}

        {item.status === 'APPROVED' && !arriveOpen && !checkInOpen && (
          <div style={{ marginTop: '1.5rem', display: 'flex', gap: '0.5rem' }}>
            <button type="button" className="admin-btn admin-btn--primary" onClick={() => setArriveOpen(true)}>
              Mark Arrived
            </button>
          </div>
        )}

        {item.status === 'ARRIVED' && !checkInOpen && !arriveOpen && (
          <div style={{ marginTop: '1.5rem' }}>
            <button type="button" className="admin-btn admin-btn--primary" onClick={() => setCheckInOpen(true)}>
              Check In Visitor
            </button>
          </div>
        )}

        {arriveOpen && (
          <div style={{ marginTop: '1.5rem', borderTop: '1px solid var(--color-slate-200)', paddingTop: '1rem' }}>
            <h3 style={{ fontSize: '0.9375rem', margin: '0 0 0.5rem' }}>Mark visitor arrived?</h3>
            <p style={{ fontSize: '0.875rem', color: 'var(--color-slate-500)', margin: '0 0 0.75rem' }}>
              {item.visitor_name} has reached reception.
            </p>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button type="button" className="admin-btn" onClick={() => setArriveOpen(false)} disabled={acting}>Cancel</button>
              <button type="button" className="admin-btn admin-btn--primary" onClick={handleArrive} disabled={acting}>
                {acting ? 'Saving…' : 'Mark Arrived'}
              </button>
            </div>
          </div>
        )}

        {checkInOpen && (
          <div style={{ marginTop: '1.5rem', borderTop: '1px solid var(--color-slate-200)', paddingTop: '1rem' }}>
            <h3 style={{ fontSize: '0.9375rem', margin: '0 0 0.5rem' }}>Check in {item.visitor_name}?</h3>
            <p style={{ fontSize: '0.875rem', color: 'var(--color-slate-500)', margin: '0 0 0.25rem' }}>Site: {item.site_name}</p>
            <p style={{ fontSize: '0.875rem', color: 'var(--color-slate-500)', margin: '0 0 0.75rem' }}>Host: {item.host_name ?? '—'}</p>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button type="button" className="admin-btn" onClick={() => setCheckInOpen(false)} disabled={acting}>Cancel</button>
              <button type="button" className="admin-btn admin-btn--primary" onClick={handleCheckIn} disabled={acting}>
                {acting ? 'Checking in…' : 'Check In'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function ExpectedTodayPage() {
  const { user } = useAuth();
  const locations = useOperationalLocations(user);
  const [site, setSite] = useState<number | undefined>();
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [items, setItems] = useState<OperationalVisit[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<OperationalVisit | null>(null);
  const [toast, setToast] = useState<{ message: string; type?: 'success' | 'error' } | null>(null);
  const searchDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (locations.length === 1) setSite(locations[0].id);
  }, [locations]);

  useEffect(() => {
    if (searchDebounce.current) clearTimeout(searchDebounce.current);
    searchDebounce.current = setTimeout(() => setSearch(searchInput), 300);
    return () => {
      if (searchDebounce.current) clearTimeout(searchDebounce.current);
    };
  }, [searchInput]);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await api.expectedToday({
        status: statusFilter,
        search: search.trim() || undefined,
        site,
        limit: 50,
      });
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load expected visitors');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, search, site]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  useOperationalPolling('expectedToday', { onRefresh: load });

  const locationLabel = site ? locations.find((l) => l.id === site)?.city ?? locations.find((l) => l.id === site)?.name : null;
  const showSiteFilter = locations.length > 1;

  return (
    <div className="vms-page-shell">
      <header className="admin-page-header">
        <div>
          <h1 className="admin-page-title">Expected Today</h1>
          {locationLabel && (
            <p className="admin-page-subtitle" style={{ marginTop: '0.15rem' }}>{locationLabel}</p>
          )}
          <p className="admin-page-subtitle">Approved visitors expected at reception today</p>
        </div>
        <button type="button" className="admin-btn" onClick={() => { setLoading(true); load(); }}>Refresh</button>
      </header>

      <div className="admin-filters">
        <input
          type="search"
          placeholder="Search visitor, company, host, reference…"
          value={searchInput}
          onChange={(e) => { setSearchInput(e.target.value); setLoading(true); }}
          aria-label="Search expected visitors"
        />
        {showSiteFilter && (
          <select value={site ?? ''} onChange={(e) => { setSite(e.target.value ? Number(e.target.value) : undefined); setLoading(true); }}>
            <option value="">All locations</option>
            {locations.map((l) => (
              <option key={l.id} value={l.id}>{l.name}</option>
            ))}
          </select>
        )}
        <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setLoading(true); }}>
          {STATUS_OPTIONS.map((s) => (
            <option key={s.id} value={s.id}>{s.label}</option>
          ))}
        </select>
      </div>

      {loading && <LoadingState message="Loading expected visitors…" />}
      {error && <ErrorState title="Unable to load" message={error} action={{ label: 'Retry', onClick: () => { setLoading(true); load(); } }} />}

      {!loading && !error && items.length === 0 && (
        <div className="empty-state">
          <h3 className="empty-state__title">No visitors expected right now</h3>
          <p className="empty-state__message">Approved visitors for today will appear here.</p>
        </div>
      )}

      {!loading && !error && items.length > 0 && (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Visitor</th>
                <th className="col-hide-mobile">Company</th>
                <th>Host</th>
                <th>Status</th>
                <th className="col-hide-mobile">Action</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} onClick={() => setSelected(item)}>
                  <td>{item.visitor_name}</td>
                  <td className="col-hide-mobile">{item.company ?? '—'}</td>
                  <td>{item.host_name ?? '—'}</td>
                  <td><StatusBadge status={item.status} /></td>
                  <td className="col-hide-mobile" style={{ fontSize: '0.8125rem' }}>
                    {item.status === 'APPROVED' ? 'Mark arrived' : item.status === 'ARRIVED' ? 'Check in' : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ padding: '0.75rem 1rem', fontSize: '0.8125rem', color: 'var(--color-slate-500)' }}>
            Showing {items.length} of {total}
          </p>
        </div>
      )}

      {selected && (
        <DetailPanel
          item={selected}
          onClose={() => setSelected(null)}
          onUpdated={() => { setLoading(true); load(); }}
          onToast={(message, type) => setToast({ message, type })}
          onRefresh={() => { setLoading(true); load(); }}
        />
      )}

      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  );
}
