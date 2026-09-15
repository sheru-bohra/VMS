import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../services/api';
import type { DashboardKpiId } from './dashboardKpi';
import type { OperationalVisit } from '../../types';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import { formatStatus } from '../../types';

interface DashboardDrillDownModalProps {
  kpiId: DashboardKpiId;
  title: string;
  count: number;
  siteId?: number;
  onClose: () => void;
}

export function DashboardDrillDownModal({
  kpiId,
  title,
  count,
  siteId,
  onClose,
}: DashboardDrillDownModalProps) {
  const [items, setItems] = useState<OperationalVisit[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await api.dashboardKpiDrillDown(kpiId, {
        location_id: siteId,
        limit: 100,
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load records');
    } finally {
      setLoading(false);
    }
  }, [kpiId, siteId]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  return (
    <div className="admin-detail-overlay" onClick={onClose}>
      <div
        className="admin-detail-panel vms-dashboard-drilldown"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="dashboard-drilldown-title"
      >
        <div className="vms-dashboard-drilldown__header">
          <h2 id="dashboard-drilldown-title">{title} ({count})</h2>
          <button type="button" className="admin-btn" onClick={onClose}>Close</button>
        </div>

        {loading && <LoadingState message="Loading records…" />}
        {error && !loading && (
          <ErrorState title="Unable to load" message={error} action={{ label: 'Retry', onClick: () => { setLoading(true); load(); } }} />
        )}
        {!loading && !error && items.length === 0 && (
          <p className="section-card__empty">No matching visitors.</p>
        )}
        {!loading && !error && items.length > 0 && (
          <>
            <div className="vms-preview-table-wrap">
              <table className="vms-preview-table">
                <thead>
                  <tr>
                    <th>Visitor</th>
                    <th>Company</th>
                    <th>Host</th>
                    <th>Location</th>
                    <th>Check-In</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id}>
                      <td>{item.visitor_name}</td>
                      <td>{item.company ?? '—'}</td>
                      <td>{item.host_name ?? '—'}</td>
                      <td>{item.site_name}</td>
                      <td>
                        {item.checked_in_at
                          ? new Date(item.checked_in_at).toLocaleString()
                          : '—'}
                      </td>
                      <td>{formatStatus(item.status)}</td>
                      <td>
                        <Link to={`/visitors`} className="vms-section-card__link" onClick={onClose}>
                          View
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {total > items.length && (
              <p className="vms-text-secondary" style={{ marginTop: '0.75rem' }}>
                Showing {items.length} of {total} records.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
