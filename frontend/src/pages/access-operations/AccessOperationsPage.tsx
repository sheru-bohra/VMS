import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../services/api';
import type { Location } from '../../types';
import { LoadingState, ErrorState, EmptyState } from '../../components/StatePanels';
import { AdminTabs } from '../../components/ui/AdminTabs';
import { StatusBadge } from '../../components/ui/StatusBadge';
import '../../styles/admin-pages.css';
import '../../styles/access-operations-page.css';

type Tab = 'active' | 'attention' | 'prints' | 'status';

interface CredentialRow {
  id: number;
  visitor_name: string;
  location_name: string;
  location_id: number;
  access_profile_name: string | null;
  status: string;
  valid_until: string | null;
  last_error_code: string | null;
  visit_id: number;
  visit_status?: string | null;
  checked_out_at?: string | null;
  severity?: string;
  reason_code?: string;
  attention_title?: string;
  attention_message?: string;
}

interface PrintJobRow {
  id: number;
  visitor_name: string;
  badge_number: string | null;
  location_name: string;
  location_id: number;
  printer_name: string | null;
  status: string;
  visit_id: number;
}

const POLL_MS = 12000;

const TAB_ITEMS = [
  { id: 'active', label: 'Active Access' },
  { id: 'attention', label: 'Needs Attention' },
  { id: 'prints', label: 'Badge Print Jobs' },
  { id: 'status', label: 'Provider Status' },
] as const;

function providerHealthLabel(health: string): string {
  const upper = health.toUpperCase();
  if (upper === 'HEALTHY' || upper === 'CONNECTED' || upper === 'READY') return 'Ready';
  if (upper === 'DEGRADED') return 'Degraded';
  if (upper === 'FAILED' || upper === 'ERROR') return 'Failed';
  if (upper === 'DISABLED') return 'Disabled';
  if (upper.includes('DEV') || upper.includes('MOCK')) return 'Development';
  return health;
}

function providerHealthStatus(health: string): string {
  const upper = health.toUpperCase();
  if (upper === 'HEALTHY' || upper === 'CONNECTED' || upper === 'READY') return 'ACTIVE';
  if (upper === 'DEGRADED') return 'REVIEW';
  if (upper === 'FAILED' || upper === 'ERROR') return 'FAILED';
  if (upper === 'DISABLED') return 'INACTIVE';
  return 'PROCESSING';
}

export function AccessOperationsPage() {
  const [tab, setTab] = useState<Tab>('active');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [locations, setLocations] = useState<Location[]>([]);
  const [credentials, setCredentials] = useState<CredentialRow[]>([]);
  const [attentionCount, setAttentionCount] = useState(0);
  const [printJobs, setPrintJobs] = useState<PrintJobRow[]>([]);
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [confirmRevoke, setConfirmRevoke] = useState<number | null>(null);
  const [filterLocationId, setFilterLocationId] = useState<number | ''>('');
  const [filterState, setFilterState] = useState('');
  const [filterAttention, setFilterAttention] = useState('');
  const [search, setSearch] = useState('');
  const hiddenRef = useRef(document.visibilityState === 'hidden');

  const load = useCallback(async (silent = false) => {
    if (!silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const locs = await api.locations();
      setLocations(locs);
      const [active, attention, jobs, st] = await Promise.all([
        api.accessCredentials(false),
        api.accessCredentials(true),
        api.badgePrintJobs(true),
        api.physicalIntegrationStatus(),
      ]);
      setAttentionCount((attention as CredentialRow[]).length);
      if (tab === 'attention') {
        setCredentials(attention as CredentialRow[]);
      } else if (tab === 'active') {
        setCredentials(active as CredentialRow[]);
      } else {
        setCredentials(active as CredentialRow[]);
      }
      setPrintJobs(jobs as PrintJobRow[]);
      setStatus(st);
    } catch (err) {
      if (!silent) setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      if (!silent) setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const onVis = () => {
      hiddenRef.current = document.visibilityState === 'hidden';
    };
    document.addEventListener('visibilitychange', onVis);
    const id = window.setInterval(() => {
      if (!hiddenRef.current) load(true);
    }, POLL_MS);
    return () => {
      document.removeEventListener('visibilitychange', onVis);
      window.clearInterval(id);
    };
  }, [load]);

  const handleRetryAccess = async (id: number) => {
    try {
      await api.retryAccessCredential(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Retry failed');
    }
  };

  const handleRevoke = async (id: number) => {
    try {
      await api.revokeAccessCredential(id);
      setConfirmRevoke(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Revoke failed');
    }
  };

  const handleRetryPrint = async (id: number) => {
    try {
      await api.retryBadgePrintJob(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Print retry failed');
    }
  };

  const filterCredentials = (rows: CredentialRow[]) => {
    const q = search.trim().toLowerCase();
    return rows.filter((c) => {
      if (filterLocationId !== '' && c.location_id !== filterLocationId) return false;
      if (filterState && c.status !== filterState) return false;
      if (filterAttention && c.reason_code !== filterAttention) return false;
      if (q && !c.visitor_name.toLowerCase().includes(q)) return false;
      return true;
    });
  };

  const filterPrintJobs = (rows: PrintJobRow[]) => {
    const q = search.trim().toLowerCase();
    return rows.filter((j) => {
      if (filterLocationId !== '' && j.location_id !== filterLocationId) return false;
      if (filterState && j.status !== filterState) return false;
      if (q && !j.visitor_name.toLowerCase().includes(q) && !(j.badge_number ?? '').toLowerCase().includes(q)) return false;
      return true;
    });
  };

  if (loading) return <LoadingState message="Loading access operations…" />;
  if (error) return <ErrorState title="Unable to load" message={error} action={{ label: 'Retry', onClick: () => load() }} />;

  const visibleCredentials = filterCredentials(credentials);
  const visiblePrintJobs = filterPrintJobs(printJobs);

  const tabs = TAB_ITEMS.map((item) => ({
    ...item,
    count: item.id === 'attention' && attentionCount > 0 ? attentionCount : undefined,
  }));

  return (
    <div className="vms-page-shell access-ops-page">
      <div className="admin-page-header">
        <div>
          <h1 className="admin-page-title">Access Operations</h1>
          <p className="admin-page-subtitle">Physical access credentials, print jobs, and provider status.</p>
        </div>
        <button type="button" className="admin-btn" onClick={() => load()}>Refresh</button>
      </div>

      <div className="access-ops-tabs">
        <AdminTabs
          tabs={tabs}
          active={tab}
          onChange={(id) => setTab(id as Tab)}
          ariaLabel="Access operations views"
        />
      </div>

      {tab !== 'status' && (
        <div className="access-ops-filters" role="search">
          <div className="access-ops-filter access-ops-filter--location">
            <span className="access-ops-filter__label" id="access-ops-location-label">Location</span>
            <select
              className="admin-input"
              aria-labelledby="access-ops-location-label"
              value={filterLocationId}
              onChange={(e) => setFilterLocationId(e.target.value === '' ? '' : Number(e.target.value))}
            >
              <option value="">All</option>
              {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          </div>
          <div className="access-ops-filter access-ops-filter--state">
            <span className="access-ops-filter__label" id="access-ops-state-label">State</span>
            <select
              className="admin-input"
              aria-labelledby="access-ops-state-label"
              value={filterState}
              onChange={(e) => setFilterState(e.target.value)}
            >
              <option value="">All</option>
              <option value="ACTIVE">ACTIVE</option>
              <option value="FAILED">FAILED</option>
              <option value="REVOCATION_PENDING">REVOCATION_PENDING</option>
              <option value="MANUAL_ACTION_REQUIRED">MANUAL_ACTION_REQUIRED</option>
            </select>
          </div>
          {tab === 'attention' && (
            <div className="access-ops-filter access-ops-filter--attention">
              <span className="access-ops-filter__label" id="access-ops-attention-label">Attention type</span>
              <select
                className="admin-input"
                aria-labelledby="access-ops-attention-label"
                value={filterAttention}
                onChange={(e) => setFilterAttention(e.target.value)}
              >
                <option value="">All</option>
                <option value="CHECKED_OUT_ACCESS_ACTIVE">Checked out + active access</option>
                <option value="REVOCATION_PENDING">Revocation pending</option>
                <option value="PROVISION_FAILED">Provision failed</option>
                <option value="MANUAL_ACCESS_REQUIRED">Manual access required</option>
              </select>
            </div>
          )}
          <div className="access-ops-filter access-ops-filter--search">
            <span className="access-ops-filter__label" id="access-ops-search-label">Search</span>
            <input
              className="admin-input"
              aria-labelledby="access-ops-search-label"
              placeholder="Visitor or badge"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>
      )}

      {tab === 'active' && (
        <section className="section-card access-ops-results" aria-label="Active access credentials">
          {visibleCredentials.length === 0 ? (
            <EmptyState
              title="No active access credentials"
              message="Active visitor access credentials will appear here."
            />
          ) : (
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Visitor</th>
                    <th>Location</th>
                    <th>Profile</th>
                    <th>Valid Until</th>
                    <th>State</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleCredentials.map((c) => (
                    <tr key={c.id}>
                      <td>{c.visitor_name}</td>
                      <td>{c.location_name}</td>
                      <td>{c.access_profile_name ?? '—'}</td>
                      <td>{c.valid_until ? new Date(c.valid_until).toLocaleString() : '—'}</td>
                      <td><StatusBadge status={c.status} /></td>
                      <td>
                        {c.status === 'ACTIVE' && (
                          <button type="button" className="admin-btn admin-btn--sm" onClick={() => setConfirmRevoke(c.id)}>
                            Revoke
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {tab === 'attention' && (
        <section className="section-card access-ops-results" aria-label="Access issues needing attention">
          {visibleCredentials.length === 0 ? (
            <EmptyState
              title="No access issues need attention"
              message="Credentials requiring follow-up will appear here."
            />
          ) : (
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Severity</th>
                    <th>Visitor</th>
                    <th>Location</th>
                    <th>Issue</th>
                    <th>Visit</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleCredentials.map((c) => (
                    <tr
                      key={c.id}
                      className={c.severity === 'URGENT' ? 'access-ops-urgent-row' : undefined}
                    >
                      <td>
                        {c.severity === 'URGENT' && <strong style={{ color: '#b91c1c' }}>URGENT</strong>}
                        {c.severity === 'ATTENTION' && 'ATTENTION'}
                        {!c.severity && '—'}
                      </td>
                      <td>{c.visitor_name}</td>
                      <td>{c.location_name}</td>
                      <td>
                        <div>{c.attention_title ?? c.status}</div>
                        {c.reason_code === 'CHECKED_OUT_ACCESS_ACTIVE' && (
                          <div style={{ fontSize: '0.8125rem', color: 'var(--color-slate-600)' }}>
                            Access still active after visitor checkout. Revocation is required.
                            {c.checked_out_at && <> Checked out: {new Date(c.checked_out_at).toLocaleString()}</>}
                            {c.valid_until && <> · Credential valid until: {new Date(c.valid_until).toLocaleString()}</>}
                          </div>
                        )}
                        {c.last_error_code && <div style={{ fontSize: '0.8125rem' }}>{c.last_error_code}</div>}
                      </td>
                      <td>{c.visit_status ?? '—'}</td>
                      <td>
                        <button type="button" className="admin-btn admin-btn--sm" onClick={() => handleRetryAccess(c.id)}>
                          {c.reason_code === 'CHECKED_OUT_ACCESS_ACTIVE' || c.status === 'REVOCATION_PENDING' ? 'Retry Revocation' : 'Retry'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {tab === 'prints' && (
        <section className="section-card access-ops-results" aria-label="Badge print jobs">
          {visiblePrintJobs.length === 0 ? (
            <EmptyState title="No badge print jobs" message="Failed or pending print jobs will appear here." />
          ) : (
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Visitor</th>
                    <th>Badge</th>
                    <th>Location</th>
                    <th>Printer</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {visiblePrintJobs.map((j) => (
                    <tr key={j.id}>
                      <td>{j.visitor_name}</td>
                      <td>{j.badge_number ?? '—'}</td>
                      <td>{j.location_name}</td>
                      <td>{j.printer_name ?? '—'}</td>
                      <td><StatusBadge status={j.status} /></td>
                      <td>
                        <div className="access-ops-table-actions">
                          {(j.status === 'FAILED' || j.status === 'MANUAL_ACTION_REQUIRED') && (
                            <button type="button" className="admin-btn admin-btn--sm" onClick={() => handleRetryPrint(j.id)}>
                              Retry
                            </button>
                          )}
                          <a className="admin-btn admin-btn--sm" href={`/badges/${j.visit_id}/print`} target="_blank" rel="noreferrer">
                            Browser Badge
                          </a>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {tab === 'status' && status && (
        <section className="section-card access-ops-results" aria-label="Provider status">
          <div className="admin-detail-row">
            <div className="admin-detail-label">Access control</div>
            <div className="admin-detail-value">
              <StatusBadge
                status={status.access_control_enabled ? 'ACTIVE' : 'INACTIVE'}
                label={status.access_control_enabled ? 'Enabled' : 'Disabled'}
              />
              <span style={{ marginLeft: '0.5rem', fontSize: '0.875rem' }}>
                {String(status.access_provider_label ?? status.access_provider)}
              </span>
            </div>
          </div>
          <div className="admin-detail-row">
            <div className="admin-detail-label">Badge printer</div>
            <div className="admin-detail-value">
              <StatusBadge
                status={status.badge_printer_enabled ? 'ACTIVE' : 'INACTIVE'}
                label={status.badge_printer_enabled ? 'Enabled' : 'Disabled'}
              />
              <span style={{ marginLeft: '0.5rem', fontSize: '0.875rem' }}>
                {String(status.badge_printer_provider_label ?? status.badge_printer_provider)}
              </span>
            </div>
          </div>
          <ul className="access-ops-provider-list" style={{ marginTop: '1rem' }}>
            {(status.locations as Array<Record<string, unknown>>).map((loc) => {
              const health = String(loc.access_health ?? 'UNKNOWN');
              return (
                <li key={String(loc.location_id)} className="access-ops-provider-row">
                  <div>
                    <div className="access-ops-provider-row__label">Location {String(loc.location_id)}</div>
                    <div className="access-ops-provider-row__detail">
                      {String(loc.access_provider_label ?? loc.access_provider)}
                    </div>
                  </div>
                  <StatusBadge status={providerHealthStatus(health)} label={providerHealthLabel(health)} />
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {confirmRevoke && (
        <div className="admin-card" style={{ marginTop: '1rem' }}>
          <p>Revoke physical access? This does not check the visitor out of VMS.</p>
          <div className="access-ops-table-actions" style={{ marginTop: '0.75rem' }}>
            <button type="button" className="admin-btn" onClick={() => setConfirmRevoke(null)}>Cancel</button>
            <button type="button" className="admin-btn admin-btn--primary" onClick={() => handleRevoke(confirmRevoke)}>
              Confirm revoke
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
