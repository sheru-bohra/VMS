import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../services/api';
import type { DashboardData, OperationalVisit } from '../../types';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import { VisitorActivityChart } from '../../components/dashboard/VisitorActivityChart';
import { useOperationalLocations } from '../../hooks/useOperationalLocations';
import { useAuth } from '../../hooks/useAuth';
import { usePreferredLocationId } from '../../hooks/usePreferredLocation';
import { useOperationalPolling } from '../../hooks/useOperationalPolling';
import { PageHeader } from '../../components/shell/PageHeader';
import { KpiStatCard } from '../../components/shell/KpiStatCard';
import { AppFooter } from '../../components/shell/AppFooter';
import { RefreshStatus } from '../../components/shell/RefreshStatus';
import { buildDashboardAttention } from '../../components/shell/dashboardAttention';
import { NavIcon } from '../../components/admin/NavIcon';
import { hasPermission } from '../../utils/permissions';
import { formatStatus } from '../../types';
import { DashboardDrillDownModal } from './DashboardDrillDownModal';
import {
  DASHBOARD_KPIS,
  buildKpiNavigationPath,
  shouldUseKpiModal,
  type DashboardKpiId,
} from './dashboardKpi';
import '../../styles/admin-pages.css';

const PERIODS = [
  { id: 'today', label: 'Today' },
  { id: 'last_7_days', label: 'Last 7 Days' },
  { id: 'last_30_days', label: 'Last 30 Days' },
  { id: 'this_month', label: 'This Month' },
];

const QUICK_ACTIONS = [
  { label: 'Register / Invite Visitor', href: '/register-visitor', icon: 'mail' as const, tone: 'violet' as const, permission: 'invitation.create' },
  { label: 'Check In', href: '/expected-today', icon: 'user-check' as const, tone: 'teal' as const, permission: 'checkin.perform' },
  { label: 'Check Out', href: '/onsite-now', icon: 'user-check' as const, tone: 'green' as const, permission: 'onsite.read' },
];

const KPI_CARD_META: Record<DashboardKpiId, {
  icon: 'clock' | 'check-circle' | 'user-check' | 'users' | 'clipboard-list' | 'triangle-alert' | 'building-2';
  tone: 'cyan' | 'amber' | 'teal' | 'green' | 'blue' | 'orange' | 'violet';
  accent: 'cyan' | 'amber' | 'green' | 'blue' | 'orange' | 'violet';
}> = {
  expected_today: { icon: 'clock', tone: 'cyan', accent: 'cyan' },
  awaiting_approval: { icon: 'check-circle', tone: 'amber', accent: 'amber' },
  checked_in_today: { icon: 'user-check', tone: 'teal', accent: 'green' },
  onsite_now: { icon: 'users', tone: 'green', accent: 'green' },
  checked_out_today: { icon: 'clipboard-list', tone: 'blue', accent: 'blue' },
  overstayed: { icon: 'triangle-alert', tone: 'orange', accent: 'orange' },
  vendor_contractor_onsite: { icon: 'building-2', tone: 'violet', accent: 'violet' },
};

function formatContextSubtitle(locationLabel: string): string {
  const now = new Date();
  const date = now.toLocaleDateString(undefined, {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
  const time = now.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
  return `${locationLabel} — ${date} ${time}`;
}

export function DashboardPage() {
  const { user, loading: authLoading } = useAuth();
  const locations = useOperationalLocations(user);
  const preferredLocationId = usePreferredLocationId(user);
  const [period, setPeriod] = useState('today');
  const [siteId, setSiteId] = useState<number | undefined>(preferredLocationId);
  const [data, setData] = useState<DashboardData | null>(null);
  const [onsitePreview, setOnsitePreview] = useState<OperationalVisit[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [activeDrillDown, setActiveDrillDown] = useState<DashboardKpiId | null>(null);

  const canOnsitePreview = user ? hasPermission(user.permissions, 'onsite.read') : false;

  useEffect(() => {
    setSiteId(preferredLocationId);
  }, [preferredLocationId]);

  useEffect(() => {
    if (locations.length === 1) {
      setSiteId(locations[0].id);
    }
  }, [locations]);

  const showAllLocationsOption = locations.length > 1;

  const load = useCallback(async (background = false) => {
    if (!background) setError(null);
    if (background) setRefreshing(true);
    try {
      const res = await api.analyticsDashboard({ period, location_id: siteId });
      setData(res);
      setLastUpdated(new Date());
      if (canOnsitePreview) {
        try {
          const onsite = await api.onsiteVisitors({
            limit: 5,
            location_id: siteId,
          });
          setOnsitePreview(onsite.items);
        } catch {
          setOnsitePreview([]);
        }
      } else {
        setOnsitePreview([]);
      }
    } catch (err) {
      if (!background) {
        setError(err instanceof Error ? err.message : 'Failed to load dashboard');
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [period, siteId, canOnsitePreview]);

  useEffect(() => {
    setLoading(true);
    load(false);
  }, [load]);

  useOperationalPolling('dashboard', {
    enabled: true,
    onRefresh: () => load(true),
  });

  const handleManualRefresh = () => {
    if (!data) {
      setLoading(true);
      load(false);
    } else {
      load(true);
    }
  };

  if (authLoading || !user) return <LoadingState message="Loading dashboard…" />;
  if (loading && !data) return <LoadingState message="Loading dashboard…" />;
  if (error && !data) {
    return (
      <ErrorState
        title="Unable to load dashboard"
        message={error}
        action={{ label: 'Retry', onClick: handleManualRefresh }}
      />
    );
  }

  const kpis = data?.kpis;
  const locationLabel = data?.range.location_label ?? 'All authorized locations';
  const attention = data ? buildDashboardAttention(data) : null;
  const visibleQuickActions = QUICK_ACTIONS.filter((a) =>
    hasPermission(user.permissions, a.permission as never),
  );

  const filterToolbar = (
    <>
      <select value={period} onChange={(e) => setPeriod(e.target.value)} aria-label="Period">
        {PERIODS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
      </select>
      <select
        value={siteId ?? ''}
        onChange={(e) => setSiteId(e.target.value ? Number(e.target.value) : undefined)}
        aria-label="Location"
      >
        {showAllLocationsOption ? <option value="">All Locations</option> : null}
        {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
      </select>
      <button type="button" className="admin-btn admin-btn--secondary" onClick={handleManualRefresh}>
        Refresh
      </button>
    </>
  );

  return (
    <div className="admin-page vms-dashboard vms-page-shell">
      <PageHeader
        title="Visitor Management Dashboard"
        subtitle={formatContextSubtitle(locationLabel)}
        icon="layout-dashboard"
        iconTone="indigo"
        actions={filterToolbar}
      />

      {attention && (
        <div className={`vms-attention-banner vms-attention-banner--${attention.severity}`}>
          <span>{attention.message}</span>
          <Link className="vms-attention-banner__link" to={attention.href}>View →</Link>
        </div>
      )}

      {visibleQuickActions.length > 0 && (
        <div className="vms-quick-actions">
          {visibleQuickActions.map((action) => (
            <Link key={action.href} to={action.href} className="vms-quick-action">
              <NavIcon name={action.icon} tone={action.tone} />
              <span>{action.label}</span>
            </Link>
          ))}
        </div>
      )}

      <div className="vms-kpi-strip" aria-label="Dashboard key metrics">
        {DASHBOARD_KPIS.map((kpi) => {
          const meta = KPI_CARD_META[kpi.id];
          const value = kpis?.[kpi.id] ?? 0;
          const useModal = shouldUseKpiModal(kpi, siteId);
          const navPath = !useModal ? buildKpiNavigationPath(kpi, siteId) : undefined;
          return (
            <KpiStatCard
              key={kpi.id}
              variant="compact"
              label={kpi.label}
              value={value}
              icon={meta.icon}
              tone={meta.tone}
              accent={meta.accent}
              ariaLabel={kpi.ariaLabel}
              to={navPath}
              onClick={useModal ? () => setActiveDrillDown(kpi.id) : undefined}
            />
          );
        })}
      </div>

      {activeDrillDown && (
        <DashboardDrillDownModal
          kpiId={activeDrillDown}
          title={DASHBOARD_KPIS.find((kpi) => kpi.id === activeDrillDown)?.label ?? 'Visitors'}
          count={kpis?.[activeDrillDown] ?? 0}
          siteId={siteId}
          onClose={() => setActiveDrillDown(null)}
        />
      )}

      {canOnsitePreview && (
        <section className="section-card" aria-labelledby="dashboard-onsite-preview">
          <div className="section-card__header vms-section-card__title-row">
            <NavIcon name="user-check" tone="green" />
            <h2 id="dashboard-onsite-preview" className="section-card__title">
              Onsite Now ({kpis?.onsite_now ?? 0})
            </h2>
            <Link to="/onsite-now" className="vms-section-card__link">View all →</Link>
          </div>
          <div className="section-card__body">
            {onsitePreview.length === 0 ? (
              <p className="section-card__empty">No visitors currently onsite.</p>
            ) : (
              <div className="vms-preview-table-wrap">
                <table className="vms-preview-table">
                  <thead>
                    <tr>
                      <th>Visitor</th>
                      <th>Company</th>
                      <th>Host</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {onsitePreview.map((v) => (
                      <tr key={v.id}>
                        <td>{v.visitor_name}</td>
                        <td>{v.company ?? '—'}</td>
                        <td>{v.host_name ?? '—'}</td>
                        <td>{formatStatus(v.status)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>
      )}

      <div className="vms-analytics-grid">
        <section className="section-card" aria-labelledby="dashboard-visitor-activity">
          <div className="section-card__header vms-section-card__title-row">
            <NavIcon name="chart-line" tone="indigo" />
            <h2 id="dashboard-visitor-activity" className="section-card__title">Visitor Activity</h2>
          </div>
          <div className="section-card__body">
            <VisitorActivityChart points={data?.visitor_trend ?? []} />
          </div>
        </section>
      </div>

      {data?.locations && data.locations.length > 0 && (
        <section className="section-card section-card__table" aria-labelledby="dashboard-location-performance">
          <div className="section-card__header vms-section-card__title-row">
            <NavIcon name="map-pin" tone="teal" />
            <h2 id="dashboard-location-performance" className="section-card__title">Location Performance</h2>
          </div>
          <div className="section-card__body">
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr><th>Location</th><th>Visitors</th><th>Check-ins</th><th>Onsite</th><th>Rejected</th></tr>
                </thead>
                <tbody>
                  {data.locations.map((l) => (
                    <tr key={l.location_id}>
                      <td>{l.location_name}</td><td>{l.visitors}</td><td>{l.check_ins}</td><td>{l.onsite}</td><td>{l.rejected}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}

      <div className="admin-two-col">
        <section className="section-card section-card--subtle">
          <h2 className="section-card__title">Visitor Types</h2>
          {(data?.visitor_types?.length ?? 0) === 0 ? (
            <p className="section-card__empty">No visitor type data for this period.</p>
          ) : (
            <ul className="vms-list">
              {data?.visitor_types?.map((t) => <li key={t.name}>{t.name}: {t.count}</li>)}
            </ul>
          )}
        </section>
        <section className="section-card section-card--subtle">
          <h2 className="section-card__title">Attention</h2>
          <ul className="vms-list vms-list--compact">
            <li>Security reviews: {data?.security_summary?.review ?? 0}</li>
            <li>Blocked: {data?.security_summary?.blocked ?? 0}</li>
            <li>Compliance review: {data?.compliance_summary?.review_required ?? 0}</li>
            <li>Non-compliant: {data?.compliance_summary?.non_compliant ?? 0}</li>
            <li>Active emergencies: {data?.active_emergencies?.length ?? 0}</li>
          </ul>
        </section>
      </div>

      <p className="vms-text-secondary vms-page-footer">
        Avg approval: {data?.approval_metrics?.average_minutes ?? 0} min · Avg visit duration: {data?.visit_duration?.average_minutes ?? 0} min
      </p>

      <AppFooter />
      <RefreshStatus lastUpdated={lastUpdated} refreshing={refreshing} />
    </div>
  );
}
