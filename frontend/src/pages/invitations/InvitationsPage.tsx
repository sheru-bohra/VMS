import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import QRCode from 'qrcode';
import { api } from '../../services/api';
import type { InvitationItem } from '../../types';
import { formatStatus } from '../../types';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import { useAuth } from '../../hooks/useAuth';
import { hasPermission } from '../../utils/permissions';
import '../../styles/admin-pages.css';

const TABS = [
  { id: 'UPCOMING', label: 'Upcoming' },
  { id: 'PENDING_APPROVAL', label: 'Pending Approval' },
  { id: 'APPROVED', label: 'Approved' },
  { id: 'COMPLETED', label: 'Completed' },
  { id: 'CANCELLED', label: 'Cancelled' },
  { id: 'ALL', label: 'All' },
];

export function InvitationsPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState('UPCOMING');
  const [items, setItems] = useState<InvitationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<InvitationItem | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const qrCanvasRef = useRef<HTMLCanvasElement>(null);

  const canCreate = user && hasPermission(user.permissions, 'invitation.create');
  const canCancel = user && hasPermission(user.permissions, 'invitation.cancel');

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await api.invitations({ tab, limit: 50 });
      setItems(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load invitations');
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  const openDetail = async (item: InvitationItem) => {
    setSelected(item);
    setDetailLoading(true);
    setCancelReason('');
    setCancelError(null);
    try {
      let detail = await api.invitationDetail(item.id);
      if (detail.has_active_invitation || detail.status === 'APPROVED') {
        try {
          detail = await api.invitationQr(item.id);
        } catch {
          // QR not yet active
        }
      }
      setSelected(detail);
    } catch (err) {
      setSelected(item);
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => {
    if (!selected?.invitation_url || !qrCanvasRef.current) return;
    QRCode.toCanvas(qrCanvasRef.current, selected.invitation_url, { width: 160, margin: 1 });
  }, [selected?.invitation_url]);

  const copyLink = (url?: string | null) => {
    if (url) navigator.clipboard?.writeText(url);
  };

  const downloadQrPng = () => {
    if (!qrCanvasRef.current || !selected) return;
    const link = document.createElement('a');
    link.download = `${selected.registration_reference ?? 'invitation'}-qr.png`;
    link.href = qrCanvasRef.current.toDataURL('image/png');
    link.click();
  };

  const handleCancel = async () => {
    if (!selected || !cancelReason.trim()) {
      setCancelError('Cancellation reason is required.');
      return;
    }
    setActionLoading(true);
    setCancelError(null);
    try {
      const updated = await api.cancelInvitation(selected.id, cancelReason.trim());
      setSelected(updated);
      setItems((prev) => prev.map((i) => (i.id === updated.id ? { ...i, ...updated } : i)));
    } catch (err) {
      setCancelError(err instanceof Error ? err.message : 'Unable to cancel visit');
    } finally {
      setActionLoading(false);
    }
  };

  const canCancelSelected =
    canCancel &&
    selected &&
    (selected.status === 'PENDING_APPROVAL' || selected.status === 'APPROVED');

  return (
    <div className="vms-page-shell">
      <header style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>Invitations</h1>
          <p style={{ fontSize: '0.875rem', color: 'var(--color-slate-500)', margin: '0.25rem 0 0' }}>Advance visitor registrations</p>
        </div>
        {canCreate && (
          <Link to="/invitations/new" className="admin-btn admin-btn--primary" style={{ textDecoration: 'none' }}>
            Create Visit
          </Link>
        )}
      </header>

      <div className="admin-tabs">
        {TABS.map((t) => (
          <button key={t.id} type="button" className={`admin-tab ${tab === t.id ? 'admin-tab--active' : ''}`} onClick={() => { setTab(t.id); setLoading(true); }}>
            {t.label}
          </button>
        ))}
      </div>

      {loading && <LoadingState message="Loading invitations…" />}
      {error && <ErrorState title="Unable to load" message={error} action={{ label: 'Retry', onClick: () => { setLoading(true); load(); } }} />}

      {!loading && !error && items.length === 0 && (
        <div className="empty-state">
          <h3 className="empty-state__title">No invitations</h3>
          <p className="empty-state__message">Advance visits matching this filter will appear here.</p>
        </div>
      )}

      {!loading && !error && items.length > 0 && (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Reference</th>
                <th>Visitor</th>
                <th className="col-hide-mobile">Company</th>
                <th className="col-hide-mobile">Location</th>
                <th className="col-hide-mobile">Host</th>
                <th>Visit Date</th>
                <th>Status</th>
                <th className="col-hide-mobile">Invitation</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} onClick={() => openDetail(item)}>
                  <td>{item.registration_reference ?? '—'}</td>
                  <td>{item.visitor_name}</td>
                  <td className="col-hide-mobile">{item.company ?? '—'}</td>
                  <td className="col-hide-mobile">{item.site_name}</td>
                  <td className="col-hide-mobile">{item.host_name ?? '—'}</td>
                  <td>{item.scheduled_start ? new Date(item.scheduled_start).toLocaleString() : '—'}</td>
                  <td>{formatStatus(item.status)}</td>
                  <td className="col-hide-mobile">{item.invitation_status}</td>
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
            {detailLoading && <p style={{ color: 'var(--color-slate-500)' }}>Loading details…</p>}
            <h2>{selected.visitor_name}</h2>
            <p style={{ color: 'var(--color-slate-500)', margin: '0 0 1rem' }}>{selected.registration_reference}</p>
            <div className="admin-detail-row"><div className="admin-detail-label">Company</div><div>{selected.company ?? '—'}</div></div>
            <div className="admin-detail-row"><div className="admin-detail-label">Location</div><div>{selected.site_name}</div></div>
            <div className="admin-detail-row"><div className="admin-detail-label">Host</div><div>{selected.host_name ?? '—'}</div></div>
            <div className="admin-detail-row"><div className="admin-detail-label">Schedule</div><div>{selected.scheduled_start ? new Date(selected.scheduled_start).toLocaleString() : '—'}</div></div>
            <div className="admin-detail-row"><div className="admin-detail-label">Purpose</div><div>{selected.purpose ?? '—'}</div></div>
            <div className="admin-detail-row"><div className="admin-detail-label">Status</div><div>{formatStatus(selected.status)}</div></div>
            <div className="admin-detail-row"><div className="admin-detail-label">Invitation</div><div>{selected.invitation_status}</div></div>
            {selected.invitation_valid_from && (
              <div className="admin-detail-row">
                <div className="admin-detail-label">Valid from</div>
                <div>{new Date(selected.invitation_valid_from).toLocaleString()}</div>
              </div>
            )}
            {selected.invitation_valid_until && (
              <div className="admin-detail-row">
                <div className="admin-detail-label">Valid until</div>
                <div>{new Date(selected.invitation_valid_until).toLocaleString()}</div>
              </div>
            )}
            {selected.created_by_email && (
              <div className="admin-detail-row">
                <div className="admin-detail-label">Created by</div>
                <div>{selected.created_by_email}</div>
              </div>
            )}
            {selected.has_active_invitation && selected.invitation_url && (
              <div style={{ marginTop: '1rem' }}>
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
                  <a href={selected.invitation_url} target="_blank" rel="noreferrer" className="admin-btn">View Invitation</a>
                  <button type="button" className="admin-btn" onClick={() => copyLink(selected.invitation_url)}>Copy Invitation Link</button>
                  <button type="button" className="admin-btn" onClick={downloadQrPng}>Download QR PNG</button>
                </div>
                <canvas ref={qrCanvasRef} aria-hidden="true" style={{ display: 'block' }} />
              </div>
            )}
            {canCancelSelected && (
              <div style={{ marginTop: '1.5rem', borderTop: '1px solid var(--color-slate-200)', paddingTop: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.8125rem', marginBottom: '0.5rem' }}>Cancel visit (reason required)</label>
                <textarea
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                  rows={3}
                  style={{ width: '100%', marginBottom: '0.5rem' }}
                  placeholder="Reason for cancellation"
                />
                {cancelError && <p style={{ color: 'var(--color-danger)', fontSize: '0.8125rem', margin: '0 0 0.5rem' }}>{cancelError}</p>}
                <button type="button" className="admin-btn admin-btn--danger" disabled={actionLoading} onClick={handleCancel}>
                  Cancel Invitation
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
