import { useCallback, useEffect, useState } from 'react';
import { api } from '../../services/api';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import '../../styles/admin-pages.css';

interface SchedulerRow {
  scheduler: string;
  lease_state: string;
  lease_expires_at: string | null;
  last_success_at: string | null;
  last_error_code: string | null;
  owner_masked: string | null;
}

interface ReadinessPayload {
  evaluated_at: string;
  runtime_instance_id: string;
  production_readiness: { environment: string; ready: boolean };
  database: Record<string, unknown>;
  schedulers: SchedulerRow[];
  queues: Record<string, unknown>;
  integrations: Array<{ key: string; label: string; status: string; detail?: string }>;
  audit_integrity: Record<string, unknown>;
  security: Record<string, unknown>;
}

function statusClass(status: string): string {
  const normalized = status.toUpperCase();
  if (['VALID', 'CONNECTED', 'CURRENT', 'HEALTHY', 'CONFIGURED', 'ACTIVE', 'READY'].includes(normalized)) {
    return 'admin-badge admin-badge--success';
  }
  if (['ATTENTION', 'STANDBY', 'COMPATIBILITY_TESTED', 'DEVELOPMENT'].includes(normalized)) {
    return 'admin-badge admin-badge--warning';
  }
  if (['CRITICAL', 'BROKEN', 'NOT_READY', 'UNAVAILABLE', 'OUTDATED'].includes(normalized)) {
    return 'admin-badge admin-badge--danger';
  }
  return 'admin-badge';
}

export function OperationsReadinessPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<ReadinessPayload | null>(null);
  const [readOnly, setReadOnly] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const me = await api.me();
      setReadOnly(me.role === 'HEAD_ADMIN');
      const readiness = await api.operationsReadiness();
      setData(readiness as ReadinessPayload);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load operations readiness');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <LoadingState message="Loading operations readiness…" />;
  if (error) return <ErrorState title="Unable to load" message={error} action={{ label: 'Retry', onClick: load }} />;
  if (!data) return <ErrorState title="No data" message="Operations readiness data is unavailable." />;

  const db = data.database;
  const queues = data.queues;

  return (
    <div className="vms-page-shell">
      <div className="admin-page-header">
        <div>
          <h1 className="admin-page-title">Operations & Deployment Readiness</h1>
          <p className="admin-page-subtitle">
            Database, scheduler coordination, processing queues, and production readiness diagnostics.
            {readOnly ? ' Read-only view.' : ''}
          </p>
        </div>
      </div>

      <div className="admin-table-wrap" style={{ marginBottom: '1rem' }}>
        <h2 className="admin-section-title">Production Readiness</h2>
        <p>
          Environment: <strong>{data.production_readiness.environment}</strong>
          <span className={statusClass(data.production_readiness.ready ? 'READY' : 'NOT_READY')}>
            {data.production_readiness.ready ? 'READY' : 'NOT_READY'}
          </span>
        </p>
        <p>Runtime instance: {data.runtime_instance_id}</p>
      </div>

      <div className="admin-table-wrap" style={{ marginBottom: '1rem' }}>
        <h2 className="admin-section-title">Database</h2>
        <table className="admin-table">
          <tbody>
            <tr>
              <th>Dialect</th>
              <td>
                {String(db.dialect)}
                <span className={statusClass(String(db.environment_label))}>{String(db.environment_label)}</span>
              </td>
            </tr>
            <tr>
              <th>Connected</th>
              <td><span className={statusClass('CONNECTED')}>CONNECTED</span></td>
            </tr>
            <tr>
              <th>Schema</th>
              <td>
                {db.schema_revision_display ? String(db.schema_revision_display) : '—'}
                <span className={statusClass(db.schema_current ? 'CURRENT' : 'OUTDATED')}>
                  {db.schema_current ? 'CURRENT' : 'OUTDATED'}
                </span>
              </td>
            </tr>
            <tr>
              <th>PostgreSQL Validation</th>
              <td><span className={statusClass(String(db.postgres_validation))}>{String(db.postgres_validation)}</span></td>
            </tr>
            <tr>
              <th>Pool Size</th>
              <td>{db.pool_size ?? '—'}</td>
            </tr>
            <tr>
              <th>Pool In Use</th>
              <td>{db.pool_in_use ?? '—'}</td>
            </tr>
            <tr>
              <th>Pool State</th>
              <td><span className={statusClass(String(db.pool_state ?? 'HEALTHY'))}>{String(db.pool_state ?? 'HEALTHY')}</span></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="admin-table-wrap" style={{ marginBottom: '1rem' }}>
        <h2 className="admin-section-title">Schedulers</h2>
        <table className="admin-table">
          <thead>
            <tr>
              <th>Scheduler</th>
              <th>Lease State</th>
              <th>Lease Expires</th>
              <th>Last Success</th>
              <th>Last Error</th>
              <th>Owner</th>
            </tr>
          </thead>
          <tbody>
            {data.schedulers.map((row) => (
              <tr key={row.scheduler}>
                <td>{row.scheduler}</td>
                <td><span className={statusClass(row.lease_state)}>{row.lease_state}</span></td>
                <td>{row.lease_expires_at ?? '—'}</td>
                <td>{row.last_success_at ?? '—'}</td>
                <td>{row.last_error_code ?? '—'}</td>
                <td>{row.owner_masked ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="admin-table-wrap" style={{ marginBottom: '1rem' }}>
        <h2 className="admin-section-title">Processing Queues</h2>
        <table className="admin-table">
          <tbody>
            <tr>
              <th>Notifications Pending</th>
              <td>{queues.notifications_pending} <span className={statusClass(String(queues.notifications_backlog_level))}>{String(queues.notifications_backlog_level)}</span></td>
            </tr>
            <tr>
              <th>Notifications Failed</th>
              <td>{queues.notifications_failed}</td>
            </tr>
            <tr>
              <th>Access Provisioning Pending</th>
              <td>{queues.access_provisioning_pending}</td>
            </tr>
            <tr>
              <th>Revocations Pending</th>
              <td>{queues.access_revocations_pending}</td>
            </tr>
            <tr>
              <th>Badge Print Pending</th>
              <td>{queues.badge_print_pending} <span className={statusClass(String(queues.physical_queue_backlog_level))}>{String(queues.physical_queue_backlog_level)}</span></td>
            </tr>
            <tr>
              <th>Badge Print Failed</th>
              <td>{queues.badge_print_failed}</td>
            </tr>
            <tr>
              <th>Retention Last Run</th>
              <td>{queues.retention_last_run_at ?? '—'}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="admin-table-wrap" style={{ marginBottom: '1rem' }}>
        <h2 className="admin-section-title">Integrations</h2>
        <table className="admin-table">
          <thead>
            <tr>
              <th>Integration</th>
              <th>Status</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {data.integrations.map((item) => (
              <tr key={item.key}>
                <td>{item.label}</td>
                <td><span className={statusClass(item.status)}>{item.status}</span></td>
                <td>{item.detail ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="admin-table-wrap">
        <h2 className="admin-section-title">Audit Integrity</h2>
        <p>
          <span className={statusClass(String(data.audit_integrity.status))}>{String(data.audit_integrity.status)}</span>
          Verified: {data.audit_integrity.verified_at ?? '—'}
        </p>
      </div>
    </div>
  );
}
