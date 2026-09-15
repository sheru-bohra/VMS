import { useCallback, useEffect, useState } from 'react';
import { api } from '../../services/api';
import type { OperationalVisit } from '../../types';
import { useAuth } from '../../hooks/useAuth';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { useOperationalLocations } from '../../hooks/useOperationalLocations';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import '../../styles/admin-pages.css';

const STATUS_OPTIONS = [
  { id: 'ALL', label: 'All statuses' },
  { id: 'PENDING_APPROVAL', label: 'Pending approval' },
  { id: 'APPROVED', label: 'Approved' },
  { id: 'ARRIVED', label: 'Arrived' },
  { id: 'ONSITE', label: 'Onsite' },
  { id: 'CHECKED_OUT', label: 'Checked out' },
  { id: 'REJECTED', label: 'Rejected' },
  { id: 'CANCELLED', label: 'Cancelled' },
  { id: 'EXPIRED', label: 'Expired' },
];

function VisitorDetailPanel({ item, onClose }: { item: OperationalVisit; onClose: () => void }) {
  return (
    <div className="admin-detail-overlay" onClick={onClose}>
      <div className="admin-detail-panel" onClick={(e) => e.stopPropagation()} role="dialog">
        <button type="button" className="admin-btn" onClick={onClose} style={{ marginBottom: '1rem' }}>Close</button>
        <h2>Visitor Record</h2>
        <p style={{ fontSize: '1.0625rem', fontWeight: 600, margin: '0 0 0.25rem' }}>{item.visitor_name}</p>
        <p style={{ fontSize: '0.875rem', color: 'var(--color-slate-500)', margin: '0 0 1rem' }}>
          {item.visitor_type ?? 'Visitor'}
          {item.company ? ` · ${item.company}` : ''}
        </p>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Reference</div>
          <div className="admin-detail-value">{item.registration_reference ?? '—'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Status</div>
          <div className="admin-detail-value"><StatusBadge status={item.status} /></div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Host</div>
          <div className="admin-detail-value">{item.host_name ?? '—'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Site</div>
          <div className="admin-detail-value">{item.site_name}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Email</div>
          <div className="admin-detail-value">{item.visitor_email ?? '—'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Mobile</div>
          <div className="admin-detail-value">{item.visitor_mobile ?? '—'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Purpose</div>
          <div className="admin-detail-value">{item.purpose ?? '—'}</div>
        </div>
        {item.scheduled_start && (
          <div className="admin-detail-row">
            <div className="admin-detail-label">Expected Arrival</div>
            <div className="admin-detail-value">{new Date(item.scheduled_start).toLocaleString()}</div>
          </div>
        )}
        {item.scheduled_end && (
          <div className="admin-detail-row">
            <div className="admin-detail-label">Expected Departure</div>
            <div className="admin-detail-value">{new Date(item.scheduled_end).toLocaleString()}</div>
          </div>
        )}
        {item.submitted_at && (
          <div className="admin-detail-row">
            <div className="admin-detail-label">Submitted</div>
            <div className="admin-detail-value">{new Date(item.submitted_at).toLocaleString()}</div>
          </div>
        )}
        <div className="admin-detail-row">
          <div className="admin-detail-label">Actual Check-In</div>
          <div className="admin-detail-value">
            {item.checked_in_at ? new Date(item.checked_in_at).toLocaleString() : '—'}
          </div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Actual Check-Out</div>
          <div className="admin-detail-value">
            {item.checked_out_at ? new Date(item.checked_out_at).toLocaleString() : '—'}
          </div>
        </div>
      </div>
    </div>
  );
}

export function VisitorsPage() {
  const { user } = useAuth();
  const locations = useOperationalLocations(user);
  const [status, setStatus] = useState('ALL');
  const [siteId, setSiteId] = useState<number | undefined>();
  const [search, setSearch] = useState('');
  const [items, setItems] = useState<OperationalVisit[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<OperationalVisit | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await api.visitorVisits({
        status: status === 'ALL' ? undefined : status,
        search: search.trim() || undefined,
        site: siteId,
        limit: 50,
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load visitors');
    } finally {
      setLoading(false);
    }
  }, [status, search, siteId]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  return (
    <div className="vms-page-shell">
      <header className="admin-page-header">
        <div>
          <h1 className="admin-page-title">Visitors</h1>
          <p className="admin-page-subtitle">Visitor records and visit history (last 120 days)</p>
        </div>
      </header>

      <div className="admin-filters" style={{ marginBottom: '1rem', display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
        <input
          type="search"
          className="admin-input"
          placeholder="Search name, company, reference…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search visitors"
        />
        <select className="admin-select" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status filter">
          {STATUS_OPTIONS.map((o) => (
            <option key={o.id} value={o.id}>{o.label}</option>
          ))}
        </select>
        {locations.length > 1 && (
          <select
            className="admin-select"
            value={siteId ?? ''}
            onChange={(e) => setSiteId(e.target.value ? Number(e.target.value) : undefined)}
            aria-label="Location filter"
          >
            <option value="">All locations</option>
            {locations.map((l) => (
              <option key={l.id} value={l.id}>{l.name}</option>
            ))}
          </select>
        )}
      </div>

      {loading && <LoadingState message="Loading visitor records…" />}
      {error && !loading && (
        <ErrorState title="Unable to load visitors" message={error} action={{ label: 'Retry', onClick: () => { setLoading(true); load(); } }} />
      )}
      {!loading && !error && items.length === 0 && (
        <div className="empty-state">
          <h3 className="empty-state__title">No visitors found</h3>
          <p className="empty-state__message">Visitor visits matching your filters will appear here.</p>
        </div>
      )}
      {!loading && !error && items.length > 0 && (
        <div className="admin-table-wrap">
          <table className="admin-table" aria-label="Visitor records">
            <thead>
              <tr>
                <th>Visitor</th>
                <th>Type</th>
                <th>Host</th>
                <th>Site</th>
                <th>Status</th>
                <th>Reference</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} onClick={() => setSelected(item)} style={{ cursor: 'pointer' }}>
                  <td>{item.visitor_name}</td>
                  <td>{item.visitor_type ?? '—'}</td>
                  <td>{item.host_name ?? '—'}</td>
                  <td>{item.site_name}</td>
                  <td><StatusBadge status={item.status} /></td>
                  <td>{item.registration_reference ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ marginTop: '0.75rem', fontSize: '0.875rem', color: 'var(--color-slate-500)' }}>
            Showing {items.length} of {total} records
          </p>
        </div>
      )}

      {selected && <VisitorDetailPanel item={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
