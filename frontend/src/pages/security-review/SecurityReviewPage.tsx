import { useCallback, useEffect, useState } from 'react';
import { api } from '../../services/api';
import type { SecurityReviewItem } from '../../types';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import { useAuth } from '../../hooks/useAuth';
import { hasPermission } from '../../utils/permissions';
import '../../styles/admin-pages.css';

const TABS = [
  { id: 'REVIEW', label: 'Needs Review' },
  { id: 'BLOCKED', label: 'Blocked' },
  { id: 'RESOLVED', label: 'Resolved' },
];

export function SecurityReviewPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState('REVIEW');
  const [items, setItems] = useState<SecurityReviewItem[]>([]);
  const [reviewCount, setReviewCount] = useState(0);
  const [blockedCount, setBlockedCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<SecurityReviewItem | null>(null);
  const [actionComment, setActionComment] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const canResolve = user && hasPermission(user.permissions, 'security_screening.resolve');

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await api.securityReviews({
        tab: tab === 'REVIEW' ? undefined : tab,
        search: search || undefined,
        limit: 50,
      });
      setItems(data.items);
      setReviewCount(data.review_count);
      setBlockedCount(data.blocked_count);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load security reviews');
    } finally {
      setLoading(false);
    }
  }, [tab, search]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  const openDetail = async (item: SecurityReviewItem) => {
    setActionComment('');
    setActionError(null);
    try {
      const detail = await api.securityReviewDetail(item.visit_id);
      setSelected(detail);
    } catch {
      setSelected(item);
    }
  };

  const handleClear = async () => {
    if (!selected) return;
    setActionLoading(true);
    setActionError(null);
    try {
      const updated = await api.clearSecurityReview(selected.visit_id, actionComment || undefined);
      setSelected(updated);
      await load();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Unable to clear visitor');
    } finally {
      setActionLoading(false);
    }
  };

  const handleBlock = async () => {
    if (!selected || !actionComment.trim()) {
      setActionError('A comment is required to keep blocked.');
      return;
    }
    setActionLoading(true);
    setActionError(null);
    try {
      const updated = await api.blockSecurityReview(selected.visit_id, actionComment.trim());
      setSelected(updated);
      await load();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Unable to block visitor');
    } finally {
      setActionLoading(false);
    }
  };

  const tabLabel = (id: string, label: string) => {
    if (id === 'REVIEW' && reviewCount) return `${label} (${reviewCount})`;
    if (id === 'BLOCKED' && blockedCount) return `${label} (${blockedCount})`;
    return label;
  };

  return (
    <div className="vms-page-shell">
      <header style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>Security Review</h1>
        <p style={{ fontSize: '0.875rem', color: 'var(--color-slate-500)', margin: '0.25rem 0 0' }}>Visits requiring security attention</p>
      </header>

      <div className="admin-tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`admin-tab ${tab === t.id ? 'admin-tab--active' : ''}`}
            onClick={() => { setTab(t.id); setLoading(true); }}
          >
            {tabLabel(t.id, t.label)}
          </button>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
        <input
          type="search"
          placeholder="Search visitor / reference"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ minWidth: '220px' }}
        />
        <button type="button" className="admin-btn" onClick={() => { setLoading(true); load(); }}>Refresh</button>
      </div>

      {loading && <LoadingState message="Loading security reviews…" />}
      {error && <ErrorState title="Unable to load" message={error} action={{ label: 'Retry', onClick: () => { setLoading(true); load(); } }} />}

      {!loading && !error && items.length === 0 && (
        <div className="empty-state">
          <h3 className="empty-state__title">No records</h3>
          <p className="empty-state__message">Security review items matching this filter will appear here.</p>
        </div>
      )}

      {!loading && !error && items.length > 0 && (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Visitor</th>
                <th className="col-hide-mobile">Company</th>
                <th>Signal</th>
                <th>Confidence</th>
                <th>State</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.visit_id} onClick={() => openDetail(item)}>
                  <td>{item.visitor_name}</td>
                  <td className="col-hide-mobile">{item.company ?? '—'}</td>
                  <td>{item.reason_summary ?? '—'}</td>
                  <td>{item.match_confidence ?? '—'}</td>
                  <td>{item.security_status}</td>
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
            <h2>{selected.visitor_name}</h2>
            <p style={{ color: 'var(--color-slate-500)', margin: '0 0 1rem' }}>{selected.registration_reference}</p>
            <div className="admin-detail-row"><div className="admin-detail-label">Company</div><div>{selected.company ?? '—'}</div></div>
            <div className="admin-detail-row"><div className="admin-detail-label">Mobile</div><div>{selected.visitor_mobile ?? '—'}</div></div>
            <div className="admin-detail-row"><div className="admin-detail-label">Email</div><div>{selected.visitor_email ?? '—'}</div></div>
            <div className="admin-detail-row"><div className="admin-detail-label">Visitor Type</div><div>{selected.visitor_type ?? '—'}</div></div>
            <div className="admin-detail-row"><div className="admin-detail-label">Host</div><div>{selected.host_name ?? '—'}</div></div>
            <div className="admin-detail-row"><div className="admin-detail-label">Location</div><div>{selected.site_name}</div></div>
            <div className="admin-detail-row"><div className="admin-detail-label">Purpose</div><div>{selected.purpose ?? '—'}</div></div>
            <div className="admin-detail-row"><div className="admin-detail-label">Visit Source</div><div>{selected.source ?? '—'}</div></div>
            <div className="admin-detail-row"><div className="admin-detail-label">Security Outcome</div><div>{selected.screening_outcome ?? selected.security_status}</div></div>
            <div className="admin-detail-row"><div className="admin-detail-label">Match Confidence</div><div>{selected.match_confidence ?? '—'}</div></div>
            {selected.signals.length > 0 && (
              <div style={{ marginTop: '1rem' }}>
                <div className="admin-detail-label">Matched Signals</div>
                <ul style={{ margin: '0.5rem 0 0', paddingLeft: '1.25rem' }}>
                  {selected.signals.map((s) => (
                    <li key={s} style={{ fontSize: '0.875rem' }}>{s}</li>
                  ))}
                </ul>
              </div>
            )}
            {canResolve && !selected.resolved && (selected.security_status === 'REVIEW' || selected.security_status === 'BLOCKED') && (
              <div style={{ marginTop: '1.5rem', borderTop: '1px solid var(--color-slate-200)', paddingTop: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.8125rem', marginBottom: '0.5rem' }}>Resolution comment</label>
                <textarea
                  value={actionComment}
                  onChange={(e) => setActionComment(e.target.value)}
                  rows={3}
                  style={{ width: '100%', marginBottom: '0.5rem' }}
                  placeholder="Optional for clear; required for keep blocked"
                />
                {actionError && <p style={{ color: 'var(--color-danger)', fontSize: '0.8125rem', margin: '0 0 0.5rem' }}>{actionError}</p>}
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <button type="button" className="admin-btn admin-btn--primary" disabled={actionLoading} onClick={handleClear}>
                    Clear to Continue
                  </button>
                  <button type="button" className="admin-btn admin-btn--danger" disabled={actionLoading} onClick={handleBlock}>
                    Keep Blocked
                  </button>
                </div>
              </div>
            )}
            {selected.resolved && (
              <div className="admin-detail-row" style={{ marginTop: '1rem' }}>
                <div className="admin-detail-label">Resolution</div>
                <div>{selected.resolution ?? 'Resolved'}</div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
