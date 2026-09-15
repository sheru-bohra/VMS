import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../../services/api';
import type { HostApprovalPublic, HostRejectionReason } from '../../types';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import '../../styles/registration.css';

export function HostApprovalPage() {
  const { token } = useParams<{ token: string }>();
  const [data, setData] = useState<HostApprovalPublic | null>(null);
  const [reasons, setReasons] = useState<HostRejectionReason[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [showReject, setShowReject] = useState(false);
  const [reasonCode, setReasonCode] = useState('');
  const [comment, setComment] = useState('');
  const [resultState, setResultState] = useState<string | null>(null);
  const [resultMessage, setResultMessage] = useState<string | null>(null);

  useEffect(() => {
    api.hostRejectionReasons()
      .then(setReasons)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!token) return;
    api.hostApprovalSummary(token)
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : 'Unable to load approval request'))
      .finally(() => setLoading(false));
  }, [token]);

  const handleApprove = async () => {
    if (!token) return;
    setActionLoading(true);
    setError(null);
    try {
      const res = await api.hostApprove(token);
      setResultState(res.state);
      setResultMessage(res.message ?? 'Visitor approved.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to approve visitor');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!token || !reasonCode) return;
    if (reasonCode === 'OTHER' && !comment.trim()) {
      setError('Please provide a short comment.');
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const res = await api.hostReject(token, reasonCode, comment.trim() || undefined);
      setResultState(res.state);
      setResultMessage(res.message ?? 'Visitor request rejected.');
      setShowReject(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to reject visitor');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) return <LoadingState message="Loading approval request…" />;
  if (error && !data) return <ErrorState title="Approval unavailable" message={error} />;

  if (resultState === 'APPROVED') {
    return (
      <div className="reg-page" style={{ padding: '1.25rem', maxWidth: '420px', margin: '0 auto' }}>
        <p style={{ color: 'var(--color-success)', fontWeight: 600, margin: '0 0 0.5rem' }}>✓ Visitor Approved</p>
        <p style={{ margin: 0 }}>{resultMessage}</p>
        <p style={{ marginTop: '1rem', color: 'var(--color-slate-600)', fontSize: '0.875rem' }}>
          The reception team can now continue with the visitor process.
        </p>
      </div>
    );
  }

  if (resultState === 'REJECTED') {
    return (
      <div className="reg-page" style={{ padding: '1.25rem', maxWidth: '420px', margin: '0 auto' }}>
        <p style={{ fontWeight: 600, margin: '0 0 0.5rem' }}>Visitor request rejected</p>
        <p style={{ margin: 0 }}>{resultMessage}</p>
      </div>
    );
  }

  if (!data) return <ErrorState title="Approval unavailable" message={error ?? 'Not found'} />;

  if (data.state !== 'PENDING') {
    return (
      <div className="reg-page" style={{ padding: '1.25rem', maxWidth: '420px', margin: '0 auto' }}>
        <h1 style={{ fontSize: '1.25rem', margin: '0 0 0.5rem' }}>Visitor Approval</h1>
        <p style={{ margin: '0 0 1rem', color: 'var(--color-slate-600)' }}>{data.message ?? 'This request has already been processed.'}</p>
        {data.visit_status && <p style={{ margin: 0 }}>Current status: {data.visit_status}</p>}
      </div>
    );
  }

  const durationLabel = data.expected_duration_minutes
    ? `${data.expected_duration_minutes >= 120 ? data.expected_duration_minutes / 60 : data.expected_duration_minutes} ${data.expected_duration_minutes >= 120 ? 'hours' : 'minutes'}`
    : '—';

  return (
    <div className="reg-page" style={{ padding: '1.25rem', maxWidth: '420px', margin: '0 auto', paddingBottom: 'env(safe-area-inset-bottom)' }}>
      <p style={{ fontSize: '0.8125rem', color: 'var(--color-slate-500)', margin: '0 0 0.25rem' }}>Visitor Approval</p>
      <h1 style={{ fontSize: '1.375rem', fontWeight: 700, margin: '0 0 0.25rem' }}>{data.visitor_name}</h1>
      {data.company && <p style={{ margin: '0 0 1rem', color: 'var(--color-slate-600)' }}>{data.company}</p>}
      <p style={{ margin: '0 0 0.25rem', fontSize: '0.875rem' }}>Would like to visit you at:</p>
      <p style={{ margin: '0 0 1rem', fontWeight: 600 }}>{data.site_name}</p>
      <div style={{ marginBottom: '0.75rem' }}>
        <div style={{ fontSize: '0.75rem', color: 'var(--color-slate-500)' }}>Purpose</div>
        <div>{data.purpose ?? '—'}</div>
      </div>
      {data.is_walk_in ? (
        <p style={{ margin: '0 0 1rem', color: 'var(--color-slate-700)', fontSize: '0.875rem' }}>
          The visitor is currently waiting at reception.
        </p>
      ) : (
        <div style={{ marginBottom: '1rem' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--color-slate-500)' }}>Scheduled visit</div>
          <div>{data.scheduled_display ?? '—'}</div>
        </div>
      )}
      <div style={{ marginBottom: '1.5rem' }}>
        <div style={{ fontSize: '0.75rem', color: 'var(--color-slate-500)' }}>Expected duration</div>
        <div>{durationLabel}</div>
      </div>

      {error && <p style={{ color: 'var(--color-danger)', fontSize: '0.875rem', marginBottom: '1rem' }}>{error}</p>}

      {!showReject && (
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button type="button" className="admin-btn admin-btn--danger" disabled={actionLoading} onClick={() => setShowReject(true)}>
            Reject
          </button>
          <button type="button" className="admin-btn admin-btn--primary" disabled={actionLoading} onClick={handleApprove}>
            Approve Visitor
          </button>
        </div>
      )}

      {showReject && (
        <div style={{ borderTop: '1px solid var(--color-slate-200)', paddingTop: '1rem' }}>
          <label style={{ display: 'block', fontSize: '0.8125rem', marginBottom: '0.5rem' }}>Rejection reason</label>
          <select value={reasonCode} onChange={(e) => setReasonCode(e.target.value)} style={{ width: '100%', marginBottom: '0.75rem' }}>
            <option value="">Select reason</option>
            {reasons.map((r) => (
              <option key={r.code} value={r.code}>{r.label}</option>
            ))}
          </select>
          {reasonCode === 'OTHER' && (
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={3}
              placeholder="Brief comment"
              style={{ width: '100%', marginBottom: '0.75rem' }}
            />
          )}
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button type="button" className="admin-btn" onClick={() => setShowReject(false)}>Cancel</button>
            <button type="button" className="admin-btn admin-btn--danger" disabled={actionLoading} onClick={handleReject}>
              Confirm Reject
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
