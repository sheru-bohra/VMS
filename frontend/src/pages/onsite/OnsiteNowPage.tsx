import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiClientError } from '../../services/api';
import { useAuth } from '../../hooks/useAuth';
import { useOperationalLocations } from '../../hooks/useOperationalLocations';
import type { OperationalVisit } from '../../types';
import { formatDuration, formatStatus } from '../../types';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import { Toast } from '../../components/admin/Toast';
import { useOperationalPolling } from '../../hooks/useOperationalPolling';
import { triggerOperationalRefresh } from '../../utils/operationalRefreshEvents';
import '../../styles/admin-pages.css';
import '../../styles/registration.css';

function formatOnsiteDuration(checkedInAt: string): string {
  const diff = Date.now() - new Date(checkedInAt).getTime();
  const mins = Math.floor(diff / 60000);
  const hrs = Math.floor(mins / 60);
  const rem = mins % 60;
  if (hrs > 0) return `${hrs}h ${String(rem).padStart(2, '0')}m`;
  return `${mins}m`;
}

function OnsiteDetailPanel({
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
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [acting, setActing] = useState(false);
  const [duration, setDuration] = useState('');

  useEffect(() => {
    if (!item.checked_in_at) return;
    const update = () => setDuration(formatOnsiteDuration(item.checked_in_at!));
    update();
    const t = setInterval(update, 60000);
    return () => clearInterval(t);
  }, [item.checked_in_at]);

  const handleCheckout = async () => {
    setActing(true);
    try {
      await api.checkOutVisit(item.id);
      onToast('Visitor checked out successfully.');
      triggerOperationalRefresh();
      setCheckoutOpen(false);
      onUpdated();
      onClose();
    } catch (err) {
      if (err instanceof ApiClientError && err.status === 409) {
        onToast(err.message, 'error');
        onRefresh();
      } else {
        onToast(err instanceof Error ? err.message : 'Checkout failed.', 'error');
      }
    } finally {
      setActing(false);
    }
  };

  return (
    <div className="admin-detail-overlay" onClick={onClose}>
      <div className="admin-detail-panel" onClick={(e) => e.stopPropagation()} role="dialog">
        <button type="button" className="admin-btn" onClick={onClose} style={{ marginBottom: '1rem' }}>Close</button>
        <h2>Onsite Visitor</h2>
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
          <div className="admin-detail-label">Arrival</div>
          <div className="admin-detail-value">
            {item.arrived_at ? new Date(item.arrived_at).toLocaleString() : '—'}
          </div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Check-in</div>
          <div className="admin-detail-value">
            {item.checked_in_at ? new Date(item.checked_in_at).toLocaleString() : '—'}
          </div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Time onsite</div>
          <div className="admin-detail-value">{duration || '—'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Registration</div>
          <div className="admin-detail-value">{item.registration_reference ?? '—'}</div>
        </div>
        {item.overstay && (
          <p style={{ fontSize: '0.8125rem', color: 'var(--color-danger)', marginTop: '0.75rem' }}>OVERSTAY</p>
        )}

        {!checkoutOpen && (
          <div style={{ marginTop: '1.5rem' }}>
            <button
              type="button"
              className="admin-btn"
              style={{ borderColor: 'var(--color-danger)', color: 'var(--color-danger)' }}
              onClick={() => setCheckoutOpen(true)}
            >
              Check Out Visitor
            </button>
          </div>
        )}

        {checkoutOpen && (
          <div style={{ marginTop: '1.5rem', borderTop: '1px solid var(--color-slate-200)', paddingTop: '1rem' }}>
            <h3 style={{ fontSize: '0.9375rem', margin: '0 0 0.5rem' }}>Check out visitor?</h3>
            <p style={{ fontSize: '0.875rem', margin: '0 0 0.25rem' }}>{item.visitor_name}</p>
            {item.checked_in_at && (
              <p style={{ fontSize: '0.875rem', color: 'var(--color-slate-500)', margin: '0 0 0.75rem' }}>
                Checked in at {new Date(item.checked_in_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </p>
            )}
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button type="button" className="admin-btn" onClick={() => setCheckoutOpen(false)} disabled={acting}>Cancel</button>
              <button
                type="button"
                className="admin-btn"
                style={{ borderColor: 'var(--color-danger)', color: 'var(--color-danger)' }}
                onClick={handleCheckout}
                disabled={acting}
              >
                {acting ? 'Checking out…' : 'Check Out'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function OnsiteNowPage() {
  const { user } = useAuth();
  const locations = useOperationalLocations(user);
  const [site, setSite] = useState<number | undefined>();
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [items, setItems] = useState<OperationalVisit[]>([]);
  const [total, setTotal] = useState(0);
  const [onsiteCount, setOnsiteCount] = useState(0);
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
      const data = await api.onsiteVisitors({
        search: search.trim() || undefined,
        site,
        limit: 50,
      });
      setItems(data.items);
      setTotal(data.total);
      setOnsiteCount(data.onsite_count);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load onsite visitors');
    } finally {
      setLoading(false);
    }
  }, [search, site]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  useOperationalPolling('onsiteNow', { onRefresh: load });

  const locationLabel = site ? locations.find((l) => l.id === site)?.city ?? locations.find((l) => l.id === site)?.name : null;
  const showSiteFilter = locations.length > 1;

  return (
    <div className="vms-page-shell">
      <header style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>Onsite Now</h1>
          {locationLabel && (
            <p style={{ fontSize: '0.8125rem', color: 'var(--color-slate-600)', margin: '0.25rem 0 0' }}>{locationLabel}</p>
          )}
          <p style={{ fontSize: '0.875rem', color: 'var(--color-slate-500)', margin: '0.25rem 0 0' }}>
            {onsiteCount} visitor{onsiteCount === 1 ? '' : 's'} onsite
          </p>
        </div>
        <button type="button" className="admin-btn" onClick={() => { setLoading(true); load(); }}>Refresh</button>
      </header>

      <div className="admin-filters">
        <input
          type="search"
          placeholder="Search visitor, company, reference…"
          value={searchInput}
          onChange={(e) => { setSearchInput(e.target.value); setLoading(true); }}
          aria-label="Search onsite visitors"
        />
        {showSiteFilter && (
          <select value={site ?? ''} onChange={(e) => { setSite(e.target.value ? Number(e.target.value) : undefined); setLoading(true); }}>
            <option value="">All locations</option>
            {locations.map((l) => (
              <option key={l.id} value={l.id}>{l.name}</option>
            ))}
          </select>
        )}
      </div>

      {loading && <LoadingState message="Loading onsite visitors…" />}
      {error && <ErrorState title="Unable to load" message={error} action={{ label: 'Retry', onClick: () => { setLoading(true); load(); } }} />}

      {!loading && !error && items.length === 0 && (
        <div className="empty-state">
          <h3 className="empty-state__title">No visitors are currently onsite</h3>
          <p className="empty-state__message">Checked-in visitors will appear here.</p>
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
                <th className="col-hide-mobile">Check-in</th>
                <th className="col-hide-mobile">Duration</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} onClick={() => setSelected(item)}>
                  <td>
                    {item.visitor_name}
                    {item.overstay && (
                      <span style={{ fontSize: '0.6875rem', color: 'var(--color-danger)', marginLeft: '0.5rem' }}>OVERSTAY</span>
                    )}
                  </td>
                  <td className="col-hide-mobile">{item.company ?? '—'}</td>
                  <td>{item.host_name ?? '—'}</td>
                  <td className="col-hide-mobile">
                    {item.checked_in_at
                      ? new Date(item.checked_in_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                      : '—'}
                  </td>
                  <td className="col-hide-mobile">
                    {item.checked_in_at ? formatOnsiteDuration(item.checked_in_at) : '—'}
                  </td>
                  <td>{formatStatus(item.status)}</td>
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
        <OnsiteDetailPanel
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
