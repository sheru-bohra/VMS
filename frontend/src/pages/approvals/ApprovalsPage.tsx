import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiClientError } from '../../services/api';
import type { ApprovalItem, RejectionReasonOption } from '../../types';
import { formatDuration } from '../../types';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { AdminTabs } from '../../components/ui/AdminTabs';
import { Toast } from '../../components/admin/Toast';
import { useOperationalPolling } from '../../hooks/useOperationalPolling';
import { triggerOperationalRefresh } from '../../utils/operationalRefreshEvents';
import '../../styles/admin-pages.css';
import '../../styles/registration.css';

const TABS = [
  { id: 'PENDING_APPROVAL', label: 'Pending' },
  { id: 'APPROVED', label: 'Approved' },
  { id: 'REJECTED', label: 'Rejected' },
  { id: 'ALL', label: 'All' },
] as const;

function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hr ago`;
  return new Date(iso).toLocaleString();
}

function complianceReadyLabel(status?: string | null): { label: string; tone: 'ready' | 'attention' } {
  if (!status || status === 'COMPLIANT' || status === 'EXPIRING') {
    return { label: 'Ready for approval', tone: 'ready' };
  }
  return { label: 'Requirements need attention', tone: 'attention' };
}

function DetailPanel({
  item,
  reasons,
  onClose,
  onUpdated,
  onToast,
  onConflict,
}: {
  item: ApprovalItem;
  reasons: RejectionReasonOption[];
  onClose: () => void;
  onUpdated: () => void;
  onToast: (msg: string, type?: 'success' | 'error') => void;
  onConflict: (item: ApprovalItem) => void;
}) {
  const [approveOpen, setApproveOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [comment, setComment] = useState('');
  const [reason, setReason] = useState('');
  const [rejectComment, setRejectComment] = useState('');
  const [acting, setActing] = useState(false);
  const [detail, setDetail] = useState<ApprovalItem>(item);
  const isPending = detail.status === 'PENDING_APPROVAL';

  useEffect(() => {
    let active = true;
    api.approvalDetail(item.id)
      .then((fresh) => { if (active) setDetail(fresh); })
      .catch(() => { if (active) setDetail(item); });
    return () => { active = false; };
  }, [item]);

  const compliance = complianceReadyLabel(detail.compliance_status);
  const complianceBlockers = (detail.compliance_signals ?? []).filter((signal) =>
    signal.startsWith('Missing: ')
    || signal.startsWith('Expired: ')
    || signal.startsWith('Pending verification: ')
    || signal.startsWith('Expiring before visit: '),
  );

  const handleApprove = async () => {
    setActing(true);
    try {
      await api.approveVisit(detail.id, comment.trim() || undefined);
      onToast('Visitor approved successfully.');
      triggerOperationalRefresh();
      setApproveOpen(false);
      onUpdated();
      onClose();
    } catch (err) {
      if (err instanceof ApiClientError && err.status === 409) {
        onConflict(detail);
        onToast('This registration was already processed by another administrator.', 'error');
      } else {
        onToast(err instanceof Error ? err.message : 'Approval failed.', 'error');
      }
    } finally {
      setActing(false);
    }
  };

  const handleReject = async () => {
    if (!reason) return;
    if (reason === 'OTHER' && !rejectComment.trim()) return;
    setActing(true);
    try {
      await api.rejectVisit(detail.id, reason, rejectComment.trim() || undefined);
      onToast('Visitor request rejected.');
      triggerOperationalRefresh();
      setRejectOpen(false);
      onUpdated();
      onClose();
    } catch (err) {
      if (err instanceof ApiClientError && err.status === 409) {
        onConflict(detail);
        onToast('This registration was already processed by another administrator.', 'error');
      } else {
        onToast(err instanceof Error ? err.message : 'Rejection failed.', 'error');
      }
    } finally {
      setActing(false);
    }
  };

  const lastApproval = detail.approval_history?.length
    ? detail.approval_history[detail.approval_history.length - 1]
    : null;

  return (
    <div className="admin-detail-overlay" onClick={onClose}>
      <div className="admin-detail-panel" onClick={(e) => e.stopPropagation()} role="dialog">
        <button type="button" className="admin-btn" onClick={onClose} style={{ marginBottom: '1rem' }}>Close</button>
        <h2>Visitor Details</h2>
        <p style={{ fontSize: '1.0625rem', fontWeight: 600, margin: '0 0 0.25rem' }}>{detail.visitor_name}</p>
        <p style={{ fontSize: '0.875rem', color: 'var(--color-slate-500)', margin: '0 0 1rem' }}>
          {detail.visitor_type ?? 'Visitor'}
          {detail.company ? ` · ${detail.company}` : ''}
        </p>

        <div className="admin-detail-row">
          <div className="admin-detail-label">Host</div>
          <div className="admin-detail-value">{detail.host_name ?? '—'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Site</div>
          <div className="admin-detail-value">{detail.site_name}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Purpose</div>
          <div className="admin-detail-value">{detail.purpose ?? '—'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Expected Stay</div>
          <div className="admin-detail-value">{formatDuration(detail.expected_duration_minutes)}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Mobile</div>
          <div className="admin-detail-value">{detail.visitor_mobile ?? '—'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Email</div>
          <div className="admin-detail-value">{detail.visitor_email ?? '—'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Policy</div>
          <div className="admin-detail-value">{detail.policy_accepted ? 'Accepted' : '—'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Submitted</div>
          <div className="admin-detail-value">
            {detail.submitted_at ? new Date(detail.submitted_at).toLocaleString() : '—'}
          </div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Registration</div>
          <div className="admin-detail-value">{detail.registration_reference ?? '—'}</div>
        </div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Status</div>
          <div className="admin-detail-value"><StatusBadge status={detail.status} /></div>
        </div>

        {isPending && (
          <div style={{ marginTop: '1rem', padding: '0.75rem', background: 'var(--color-slate-100)', borderRadius: 'var(--radius-md)' }}>
            <div className="admin-detail-label">Compliance</div>
            <div className="admin-detail-value" style={{ fontSize: '0.875rem' }}>
              {compliance.tone === 'ready' ? '✓ ' : '⚠ '}
              {compliance.label}
            </div>
            {complianceBlockers.length > 0 && (
              <ul style={{ margin: '0.5rem 0 0', paddingLeft: '1.1rem', fontSize: '0.8125rem', color: 'var(--color-slate-600)' }}>
                {complianceBlockers.map((signal) => (
                  <li key={signal}>{signal}</li>
                ))}
              </ul>
            )}
          </div>
        )}

        {lastApproval && (
          <div style={{ marginTop: '1rem', padding: '0.75rem', background: 'var(--color-slate-100)', borderRadius: 'var(--radius-md)' }}>
            <div className="admin-detail-label">{formatStatus(lastApproval.decision)}</div>
            <div className="admin-detail-value" style={{ fontSize: '0.875rem' }}>
              by {lastApproval.actor_email ?? 'Unknown'}
              {lastApproval.actor_role ? ` · ${lastApproval.actor_role.replace('_', ' ')}` : ''}
            </div>
            {lastApproval.created_at && (
              <div style={{ fontSize: '0.8125rem', color: 'var(--color-slate-500)' }}>
                {new Date(lastApproval.created_at).toLocaleString()}
              </div>
            )}
            {lastApproval.reason_code && (
              <div style={{ fontSize: '0.8125rem', marginTop: '0.25rem' }}>
                Reason: {lastApproval.reason_code.replace(/_/g, ' ')}
              </div>
            )}
            {lastApproval.comment && (
              <div style={{ fontSize: '0.8125rem', marginTop: '0.25rem' }}>{lastApproval.comment}</div>
            )}
          </div>
        )}

        {isPending && !approveOpen && !rejectOpen && (
          <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.5rem' }}>
            <button type="button" className="admin-btn" style={{ flex: 1, borderColor: 'var(--color-danger)', color: 'var(--color-danger)' }} onClick={() => setRejectOpen(true)}>
              Reject
            </button>
            <button type="button" className="admin-btn admin-btn--primary" style={{ flex: 1 }} onClick={() => setApproveOpen(true)}>
              Approve Visitor
            </button>
          </div>
        )}

        {approveOpen && (
          <div style={{ marginTop: '1.5rem', borderTop: '1px solid var(--color-slate-200)', paddingTop: '1rem' }}>
            <h3 style={{ fontSize: '0.9375rem', margin: '0 0 0.5rem' }}>Approve visitor?</h3>
            <p style={{ fontSize: '0.875rem', color: 'var(--color-slate-500)', margin: '0 0 0.75rem' }}>
              {detail.visitor_name} will be approved to proceed with this visit.
            </p>
            <label className="admin-detail-label" htmlFor="approve-comment">Comment (optional)</label>
            <textarea id="approve-comment" className="reg-form-textarea" rows={2} value={comment} onChange={(e) => setComment(e.target.value)} style={{ marginBottom: '0.75rem' }} />
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button type="button" className="admin-btn" onClick={() => setApproveOpen(false)} disabled={acting}>Cancel</button>
              <button type="button" className="admin-btn admin-btn--primary" onClick={handleApprove} disabled={acting}>
                {acting ? 'Approving…' : 'Approve'}
              </button>
            </div>
          </div>
        )}

        {rejectOpen && (
          <div style={{ marginTop: '1.5rem', borderTop: '1px solid var(--color-slate-200)', paddingTop: '1rem' }}>
            <h3 style={{ fontSize: '0.9375rem', margin: '0 0 0.75rem' }}>Reject visitor request</h3>
            <label className="admin-detail-label" htmlFor="reject-reason">Reason *</label>
            <select id="reject-reason" className="reg-form-select" value={reason} onChange={(e) => setReason(e.target.value)} style={{ marginBottom: '0.75rem' }}>
              <option value="">Select reason…</option>
              {reasons.map((r) => (
                <option key={r.code} value={r.code}>{r.label}</option>
              ))}
            </select>
            <label className="admin-detail-label" htmlFor="reject-comment">Additional comment</label>
            <textarea id="reject-comment" className="reg-form-textarea" rows={2} value={rejectComment} onChange={(e) => setRejectComment(e.target.value)} style={{ marginBottom: '0.75rem' }} />
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button type="button" className="admin-btn" onClick={() => setRejectOpen(false)} disabled={acting}>Cancel</button>
              <button
                type="button"
                className="admin-btn"
                style={{ borderColor: 'var(--color-danger)', color: 'var(--color-danger)' }}
                onClick={handleReject}
                disabled={acting || !reason || (reason === 'OTHER' && !rejectComment.trim())}
              >
                {acting ? 'Rejecting…' : 'Reject Request'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function ApprovalsPage() {
  const [tab, setTab] = useState<string>('PENDING_APPROVAL');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [items, setItems] = useState<ApprovalItem[]>([]);
  const [pendingCount, setPendingCount] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<ApprovalItem | null>(null);
  const [reasons, setReasons] = useState<RejectionReasonOption[]>([]);
  const [toast, setToast] = useState<{ message: string; type?: 'success' | 'error' } | null>(null);
  const searchDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    api.rejectionReasons().then(setReasons).catch(() => {});
  }, []);

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
      const data = await api.approvals({
        status: tab,
        search: search.trim() || undefined,
        limit: 50,
      });
      setItems(data.items);
      setTotal(data.total);
      setPendingCount(data.pending_count);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load approvals');
    } finally {
      setLoading(false);
    }
  }, [tab, search]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  useOperationalPolling('approvals', { onRefresh: load });

  const handleConflict = async (item: ApprovalItem) => {
    try {
      const detail = await api.approvalDetail(item.id);
      setSelected(detail);
      load();
    } catch {
      setSelected(null);
      load();
    }
  };

  return (
    <div className="vms-page-shell">
      <header className="admin-page-header">
        <div>
          <h1 className="admin-page-title">Approvals</h1>
          <p className="admin-page-subtitle">Review and process visitor registration requests</p>
        </div>
        <button type="button" className="admin-btn" onClick={() => { setLoading(true); load(); }}>Refresh</button>
      </header>

      <AdminTabs
        tabs={TABS.map((t) => ({
          id: t.id,
          label: t.label,
          count: t.id === 'PENDING_APPROVAL' && pendingCount > 0 ? pendingCount : undefined,
        }))}
        active={tab}
        onChange={(id) => { setTab(id); setLoading(true); }}
        ariaLabel="Approval status"
      />

      <div className="admin-filters">
        <input
          type="search"
          placeholder="Search visitor, company, reference…"
          value={searchInput}
          onChange={(e) => { setSearchInput(e.target.value); setLoading(true); }}
          aria-label="Search approvals"
        />
      </div>

      {loading && <LoadingState message="Loading approval queue…" />}
      {error && <ErrorState title="Unable to load" message={error} action={{ label: 'Retry', onClick: () => { setLoading(true); load(); } }} />}

      {!loading && !error && items.length === 0 && (
        <div className="empty-state">
          <h3 className="empty-state__title">No requests</h3>
          <p className="empty-state__message">
            {tab === 'PENDING_APPROVAL' ? 'No pending approvals at this time.' : 'No records match this filter.'}
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
                <th>Host</th>
                <th className="col-hide-mobile">Submitted</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} onClick={() => setSelected(item)}>
                  <td>{item.visitor_name}</td>
                  <td className="col-hide-mobile">{item.company ?? '—'}</td>
                  <td>{item.host_name ?? '—'}</td>
                  <td className="col-hide-mobile">
                    {item.submitted_at ? formatRelativeTime(item.submitted_at) : '—'}
                  </td>
                  <td><StatusBadge status={item.status} /></td>
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
          reasons={reasons}
          onClose={() => setSelected(null)}
          onUpdated={() => { setLoading(true); load(); }}
          onToast={(message, type) => setToast({ message, type })}
          onConflict={handleConflict}
        />
      )}

      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  );
}
