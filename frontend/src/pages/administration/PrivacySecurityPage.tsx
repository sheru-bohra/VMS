import { useCallback, useEffect, useState } from 'react';
import { api } from '../../services/api';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import { AdminTabs } from '../../components/ui/AdminTabs';
import { StatusBadge } from '../../components/ui/StatusBadge';
import {
  formatRetentionAction,
  formatRetentionCategory,
  formatReadinessStatus,
} from '../../utils/displayLabels';
import '../../styles/admin-pages.css';

type Tab = 'retention' | 'readiness' | 'audit' | 'files';

const TABS = [
  { id: 'retention', label: 'Data Retention' },
  { id: 'readiness', label: 'Security Readiness' },
  { id: 'audit', label: 'Audit Integrity' },
  { id: 'files', label: 'File Security' },
];

interface RetentionPolicy {
  id: number;
  data_category: string;
  scope_type: string;
  location_id: number | null;
  location_name: string | null;
  retention_days: number;
  action: string;
  is_active: boolean;
}

export function PrivacySecurityPage() {
  const [tab, setTab] = useState<Tab>('retention');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [canManage, setCanManage] = useState(false);
  const [canExecute, setCanExecute] = useState(false);
  const [policies, setPolicies] = useState<RetentionPolicy[]>([]);
  const [readiness, setReadiness] = useState<Record<string, unknown> | null>(null);
  const [audit, setAudit] = useState<Record<string, unknown> | null>(null);
  const [fileSecurity, setFileSecurity] = useState<Record<string, unknown> | null>(null);
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const [confirmPolicyId, setConfirmPolicyId] = useState<number | null>(null);
  const [runResult, setRunResult] = useState<Record<string, unknown> | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const me = await api.me();
      setCanManage(me.permissions.includes('privacy.retention.manage'));
      setCanExecute(me.permissions.includes('privacy.retention.execute'));
      const [p, r, a, f] = await Promise.all([
        api.retentionPolicies(),
        api.securityReadiness(),
        api.auditIntegrity(),
        api.fileSecurityStatus(),
      ]);
      setPolicies(p);
      setReadiness(r);
      setAudit(a);
      setFileSecurity(f);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handlePreview = async (policyId: number) => {
    try {
      const result = await api.retentionPreview(policyId);
      setPreview(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Preview failed');
    }
  };

  const handleExecute = async (policyId: number) => {
    try {
      const result = await api.retentionExecute(policyId);
      setRunResult(result);
      setConfirmPolicyId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Retention run failed');
    }
  };

  if (loading) return <LoadingState message="Loading privacy & security…" />;
  if (error) return <ErrorState title="Unable to load" message={error} action={{ label: 'Retry', onClick: load }} />;

  const auditStatus = String(audit?.status ?? '');

  return (
    <div className="vms-page-shell">
      <div className="admin-page-header">
        <div>
          <h1 className="admin-page-title">Privacy & Security</h1>
          <p className="admin-page-subtitle">Retention configuration, audit integrity, and security readiness.</p>
        </div>
      </div>

      <AdminTabs
        tabs={TABS}
        active={tab}
        onChange={(id) => setTab(id as Tab)}
        ariaLabel="Privacy and security sections"
      />

      {tab === 'retention' && (
        <div className="section-card">
          <div className="admin-table-wrap" style={{ marginBottom: 0 }}>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Scope</th>
                  <th>Retention</th>
                  <th>Action</th>
                  <th>Status</th>
                  {canExecute && <th>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {policies.map((p) => (
                  <tr key={p.id}>
                    <td>{formatRetentionCategory(p.data_category)}</td>
                    <td>{p.scope_type === 'LOCATION' ? p.location_name ?? 'Location' : 'Global'}</td>
                    <td>{p.retention_days} days</td>
                    <td>
                      <span className="vms-info-chip">{formatRetentionAction(p.action)}</span>
                    </td>
                    <td>
                      <StatusBadge
                        status={p.is_active ? 'ACTIVE' : 'INACTIVE'}
                        label={p.is_active ? 'Active' : 'Inactive'}
                      />
                    </td>
                    {canExecute && (
                      <td>
                        <div className="vms-table-actions">
                          <button
                            type="button"
                            className="admin-btn admin-btn--sm"
                            onClick={() => handlePreview(p.id)}
                          >
                            Preview
                          </button>
                          <button
                            type="button"
                            className="admin-btn admin-btn--sm admin-btn--primary"
                            onClick={() => setConfirmPolicyId(p.id)}
                          >
                            Run
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {preview && (
            <div className="admin-card" style={{ marginTop: '1rem' }}>
              <p>
                Eligible: {String(preview.eligible_count)} · Skipped: {String(preview.skipped_count)}
              </p>
            </div>
          )}
          {confirmPolicyId && (
            <div className="admin-card" style={{ marginTop: '1rem' }}>
              <p>Run retention policy? This action cannot be automatically undone.</p>
              <div className="vms-table-actions" style={{ marginTop: '0.75rem' }}>
                <button type="button" className="admin-btn" onClick={() => setConfirmPolicyId(null)}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="admin-btn admin-btn--primary"
                  onClick={() => handleExecute(confirmPolicyId)}
                >
                  Confirm run
                </button>
              </div>
            </div>
          )}
          {runResult && (
            <div className="admin-card" style={{ marginTop: '1rem' }}>
              <p>
                Run {String(runResult.status)} — processed {String(runResult.processed_count)} / eligible{' '}
                {String(runResult.eligible_count)}
              </p>
            </div>
          )}
          {!canManage && (
            <p style={{ fontSize: '0.875rem', color: 'var(--color-slate-500)', marginTop: '1rem' }}>
              Read-only retention view.
            </p>
          )}
        </div>
      )}

      {tab === 'readiness' && readiness && (
        <div className="section-card">
          <div className="admin-page-header" style={{ marginBottom: '1rem' }}>
            <div>
              <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: 0 }}>Security Readiness</h2>
              <p className="admin-page-subtitle" style={{ marginTop: '0.25rem' }}>
                Environment: {String(readiness.environment)} · Overall: {String(readiness.ready)}
              </p>
            </div>
          </div>
          <ul className="vms-readiness-list">
            {(readiness.checks as Array<{ label: string; status: string; detail?: string }>).map((c) => (
              <li key={c.label} className="vms-readiness-row">
                <div>
                  <div className="vms-readiness-row__label">{c.label}</div>
                  {c.detail && <div className="vms-readiness-row__detail">{c.detail}</div>}
                </div>
                <StatusBadge status={c.status} label={formatReadinessStatus(c.status)} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {tab === 'audit' && audit && (
        <div className="section-card">
          <div className="admin-page-header" style={{ marginBottom: '1rem' }}>
            <div>
              <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: 0 }}>Audit Integrity</h2>
              <p className="admin-page-subtitle" style={{ marginTop: '0.25rem' }}>
                Chain verification and sealed event counts
              </p>
            </div>
            <StatusBadge status={auditStatus} label={auditStatus === 'VALID' ? 'Valid' : auditStatus} />
          </div>
          <div className="admin-detail-row">
            <div className="admin-detail-label">Sealed events</div>
            <div className="admin-detail-value">{String(audit.sealed_count)}</div>
          </div>
          <div className="admin-detail-row">
            <div className="admin-detail-label">Unsealed legacy</div>
            <div className="admin-detail-value">{String(audit.legacy_count)}</div>
          </div>
          {audit.status === 'BROKEN' && (
            <p className="login-card__error" style={{ marginTop: '1rem' }}>
              Integrity verification failed. Administrative investigation required.
            </p>
          )}
        </div>
      )}

      {tab === 'files' && fileSecurity && (
        <div className="section-card">
          <div className="admin-page-header" style={{ marginBottom: '1rem' }}>
            <div>
              <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: 0 }}>File Security</h2>
              <p className="admin-page-subtitle" style={{ marginTop: '0.25rem' }}>
                Scanner and encryption configuration
              </p>
            </div>
          </div>
          <div className="admin-detail-row">
            <div className="admin-detail-label">Scanner provider</div>
            <div className="admin-detail-value">{String(fileSecurity.scanner_provider)}</div>
          </div>
          <div className="admin-detail-row">
            <div className="admin-detail-label">Encryption enabled</div>
            <div className="admin-detail-value">
              <StatusBadge
                status={fileSecurity.encryption_enabled ? 'ACTIVE' : 'INACTIVE'}
                label={fileSecurity.encryption_enabled ? 'Enabled' : 'Disabled'}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
