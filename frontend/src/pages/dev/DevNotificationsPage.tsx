import { useEffect, useState } from 'react';
import { api } from '../../services/api';
import type { NotificationItem } from '../../types';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import { useAuth } from '../../hooks/useAuth';
import '../../styles/admin-pages.css';

export function DevNotificationsPage() {
  const { user, loading: authLoading } = useAuth();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<NotificationItem | null>(null);

  useEffect(() => {
    if (!user?.is_owner) {
      setLoading(false);
      return;
    }
    api.devNotifications()
      .then((data) => setItems(data.items))
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load dev notifications'))
      .finally(() => setLoading(false));
  }, [user]);

  if (authLoading || loading) return <LoadingState message="Loading dev outbox…" />;
  if (!user?.is_owner) return <ErrorState title="Access denied" message="Development outbox is available to Global Admin only." />;
  if (error) return <ErrorState title="Unable to load" message={error} />;

  return (
    <div className="vms-page-shell" style={{ padding: '1.5rem', maxWidth: '960px', margin: '0 auto' }}>
      <h1 style={{ fontSize: '1.25rem', margin: '0 0 0.25rem' }}>Dev Notification Outbox</h1>
      <p style={{ color: 'var(--color-slate-500)', fontSize: '0.875rem', margin: '0 0 1.5rem' }}>
        Development email preview — no real email is sent.
      </p>
      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Recipient</th>
              <th>Subject</th>
              <th>Status</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} onClick={() => setSelected(item)}>
                <td>{item.notification_type}</td>
                <td>{item.recipient}</td>
                <td>{item.subject ?? '—'}</td>
                <td>{item.status}</td>
                <td>{item.created_at ? new Date(item.created_at).toLocaleString() : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selected && (
        <div className="admin-detail-overlay" onClick={() => setSelected(null)}>
          <div className="admin-detail-panel" onClick={(e) => e.stopPropagation()}>
            <button type="button" className="admin-btn" onClick={() => setSelected(null)} style={{ marginBottom: '1rem' }}>Close</button>
            <h2>{selected.subject}</h2>
            <p style={{ color: 'var(--color-slate-500)' }}>To: {selected.recipient}</p>
            <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.875rem', marginTop: '1rem', background: 'var(--color-slate-50)', padding: '1rem', borderRadius: '8px' }}>
              {selected.body_preview ?? 'No preview'}
            </pre>
            {selected.dev_action_url && (
              <a href={selected.dev_action_url} className="admin-btn admin-btn--primary" style={{ marginTop: '1rem', display: 'inline-block', textDecoration: 'none' }}>
                Open Approval Link
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
