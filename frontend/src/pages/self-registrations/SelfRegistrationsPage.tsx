import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../../services/api';
import type { SelfRegistration } from '../../types';
import { formatDuration } from '../../types';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { AdminTabs } from '../../components/ui/AdminTabs';
import { SelfRegistrationSubnav } from './SelfRegistrationSubnav';
import '../../styles/admin-pages.css';

const TABS = [
  { id: 'PENDING_APPROVAL', label: 'Pending' },
  { id: 'APPROVED', label: 'Approved' },
  { id: 'REJECTED', label: 'Rejected' },
  { id: 'ALL', label: 'All' },
] as const;

const POLL_INTERVAL = 30000;

function DetailPanel({
  registration,
  onClose,
}: {
  registration: SelfRegistration;
  onClose: () => void;
}) {
  return (
    <div className="admin-detail-overlay" onClick={onClose}>
      <div className="admin-detail-panel" onClick={(e) => e.stopPropagation()} role="dialog" aria-labelledby="reg-detail-title">
        <button type="button" className="admin-btn" onClick={onClose} style={{ marginBottom: '1rem' }}>Close</button>
        <h2 id="reg-detail-title">Registration Details</h2>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Reference</div>
          <div className="admin-detail-value">{registration.registration_reference ?? '—'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Status</div>
          <div className="admin-detail-value"><StatusBadge status={registration.status} /></div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Visitor</div>
          <div className="admin-detail-value">{registration.visitor_name}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Mobile</div>
          <div className="admin-detail-value">{registration.visitor_mobile ?? '—'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Email</div>
          <div className="admin-detail-value">{registration.visitor_email ?? '—'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Company</div>
          <div className="admin-detail-value">{registration.company ?? '—'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Visitor Type</div>
          <div className="admin-detail-value">{registration.visitor_type ?? '—'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Host</div>
          <div className="admin-detail-value">{registration.host_name ?? '—'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Site</div>
          <div className="admin-detail-value">{registration.site_name}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Purpose</div>
          <div className="admin-detail-value">{registration.purpose ?? '—'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Expected Stay</div>
          <div className="admin-detail-value">{formatDuration(registration.expected_duration_minutes)}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Policy Accepted</div>
          <div className="admin-detail-value">{registration.policy_accepted ? 'Yes' : 'No'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Submitted</div>
          <div className="admin-detail-value">
            {new Date(registration.submitted_at).toLocaleString()}
          </div>
        </div>
        <p style={{ fontSize: '0.8125rem', color: 'var(--color-slate-500)', marginTop: '1.5rem' }}>
          Approval actions will be available in the next implementation phase.
        </p>
      </div>
    </div>
  );
}

export function SelfRegistrationsPage() {
  const [searchParams] = useSearchParams();
  const tabParam = searchParams.get('tab');
  const siteParam = searchParams.get('site');
  const [tab, setTab] = useState<string>(tabParam || 'PENDING_APPROVAL');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [items, setItems] = useState<SelfRegistration[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<SelfRegistration | null>(null);
  const searchDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);

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
      const data = await api.selfRegistrations({
        status: tab,
        search: search.trim() || undefined,
        site: siteParam ? Number(siteParam) : undefined,
        limit: 50,
      });
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load registrations');
    } finally {
      setLoading(false);
    }
  }, [tab, search, siteParam]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  useEffect(() => {
    const onVisibility = () => {
      if (document.hidden) return;
      load();
    };
    const timer = setInterval(() => {
      if (!document.hidden) load();
    }, POLL_INTERVAL);
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [load]);

  const handleSearchChange = (value: string) => {
    setSearchInput(value);
    setLoading(true);
  };

  const openDetail = async (item: SelfRegistration) => {
    try {
      const detail = await api.selfRegistrationDetail(item.id);
      setSelected(detail);
    } catch {
      setSelected(item);
    }
  };

  return (
    <div className="vms-page-shell">
      <SelfRegistrationSubnav />
      <header className="admin-page-header">
        <div>
          <h1 className="admin-page-title">Self Registrations</h1>
          <p className="admin-page-subtitle">Walk-in and QR self-registration requests</p>
        </div>
        <button type="button" className="admin-btn" onClick={() => { setLoading(true); load(); }}>
          Refresh
        </button>
      </header>

      <AdminTabs
        tabs={TABS.map((t) => ({ id: t.id, label: t.label }))}
        active={tab}
        onChange={(id) => { setTab(id); setLoading(true); }}
        ariaLabel="Registration status"
      />

      <div className="admin-filters">
        <input
          type="search"
          placeholder="Search visitor, reference, host…"
          value={searchInput}
          onChange={(e) => handleSearchChange(e.target.value)}
          aria-label="Search registrations"
        />
      </div>

      {loading && <LoadingState message="Loading registrations…" />}
      {error && <ErrorState title="Unable to load" message={error} action={{ label: 'Retry', onClick: () => { setLoading(true); load(); } }} />}

      {!loading && !error && items.length === 0 && (
        <div className="empty-state">
          <h3 className="empty-state__title">No registrations</h3>
          <p className="empty-state__message">
            {tab === 'PENDING_APPROVAL' ? 'No pending self-registrations at this time.' : 'No records match this filter.'}
          </p>
        </div>
      )}

      {!loading && !error && items.length > 0 && (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Visitor</th>
                <th className="col-hide-mobile">Company</th>
                <th className="col-hide-mobile">Type</th>
                <th>Host</th>
                <th className="col-hide-mobile">Site</th>
                <th className="col-hide-mobile">Submitted</th>
                <th>Status</th>
                <th className="col-hide-mobile">Reference</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} onClick={() => openDetail(item)}>
                  <td>{item.visitor_name}</td>
                  <td className="col-hide-mobile">{item.company ?? '—'}</td>
                  <td className="col-hide-mobile">{item.visitor_type ?? '—'}</td>
                  <td>{item.host_name ?? '—'}</td>
                  <td className="col-hide-mobile">{item.site_name}</td>
                  <td className="col-hide-mobile">
                    {new Date(item.submitted_at).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })}
                  </td>
                  <td><StatusBadge status={item.status} /></td>
                  <td className="col-hide-mobile">{item.registration_reference ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ padding: '0.75rem 1rem', fontSize: '0.8125rem', color: 'var(--color-slate-500)' }}>
            Showing {items.length} of {total}
          </p>
        </div>
      )}

      {selected && <DetailPanel registration={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
