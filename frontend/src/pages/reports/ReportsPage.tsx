import { useCallback, useEffect, useState } from 'react';
import { api } from '../../services/api';
import type { ReportVisitRow } from '../../types';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import { useOperationalLocations } from '../../hooks/useOperationalLocations';
import { useAuth } from '../../hooks/useAuth';
import { hasPermission } from '../../utils/permissions';
import '../../styles/admin-pages.css';

function defaultRange() {
  const to = new Date();
  const from = new Date();
  from.setDate(from.getDate() - 7);
  return { from: from.toISOString().slice(0, 10), to: to.toISOString().slice(0, 10) };
}

export function ReportsPage() {
  const { user } = useAuth();
  const permissions = user?.permissions ?? [];
  const locations = useOperationalLocations(user);
  const [range, setRange] = useState(defaultRange());
  const [filters, setFilters] = useState({
    location_id: '',
    visitor_type_id: '',
    company: '',
    status: '',
    source: '',
    security_status: '',
    compliance_status: '',
    registration_reference: '',
  });
  const [items, setItems] = useState<ReportVisitRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState<string | null>(null);

  const canExportCsv = hasPermission(permissions, 'reports.export') || hasPermission(permissions, 'reports.export.csv');
  const canExportXlsx = hasPermission(permissions, 'reports.export') || hasPermission(permissions, 'reports.export.xlsx');

  const buildParams = () => ({
    from: `${range.from}T00:00:00Z`,
    to: `${range.to}T23:59:59Z`,
    location_id: filters.location_id ? Number(filters.location_id) : undefined,
    visitor_type_id: filters.visitor_type_id ? Number(filters.visitor_type_id) : undefined,
    company: filters.company || undefined,
    status: filters.status || undefined,
    source: filters.source || undefined,
    security_status: filters.security_status || undefined,
    compliance_status: filters.compliance_status || undefined,
    registration_reference: filters.registration_reference || undefined,
    page,
    page_size: pageSize,
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.reportVisits(buildParams());
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load reports');
    } finally {
      setLoading(false);
    }
  }, [range, filters, page, pageSize]);

  useEffect(() => { load(); }, [load]);

  const exportFile = async (format: 'csv' | 'xlsx') => {
    setExporting(format);
    try {
      const loc = locations.find((l) => l.id === Number(filters.location_id));
      const blob = await api.exportReportVisits(format, {
        ...buildParams(),
        location_label: loc?.name,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `VMS_Visitor_Report_${range.from}_to_${range.to}.${format === 'csv' ? 'csv' : 'xlsx'}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="vms-page-shell">
      <h1 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '1rem' }}>Reports</h1>

      <div className="admin-filters" style={{ marginBottom: '1rem', display: 'grid', gap: '0.5rem', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))' }}>
        <label style={{ fontSize: '0.8125rem' }}>From<input type="date" value={range.from} onChange={(e) => setRange((r) => ({ ...r, from: e.target.value }))} style={{ width: '100%' }} /></label>
        <label style={{ fontSize: '0.8125rem' }}>To<input type="date" value={range.to} onChange={(e) => setRange((r) => ({ ...r, to: e.target.value }))} style={{ width: '100%' }} /></label>
        <label style={{ fontSize: '0.8125rem' }}>Location
          <select value={filters.location_id} onChange={(e) => setFilters((f) => ({ ...f, location_id: e.target.value }))} style={{ width: '100%' }}>
            <option value="">All</option>
            {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
        </label>
        <label style={{ fontSize: '0.8125rem' }}>Status
          <select value={filters.status} onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))} style={{ width: '100%' }}>
            <option value="">All</option>
            <option value="PENDING_APPROVAL">Pending Approval</option>
            <option value="APPROVED">Approved</option>
            <option value="ONSITE">Onsite</option>
            <option value="CHECKED_OUT">Checked Out</option>
            <option value="REJECTED">Rejected</option>
          </select>
        </label>
        <label style={{ fontSize: '0.8125rem' }}>Company<input value={filters.company} onChange={(e) => setFilters((f) => ({ ...f, company: e.target.value }))} style={{ width: '100%' }} /></label>
        <label style={{ fontSize: '0.8125rem' }}>Reference<input value={filters.registration_reference} onChange={(e) => setFilters((f) => ({ ...f, registration_reference: e.target.value }))} style={{ width: '100%' }} /></label>
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        <button type="button" className="admin-btn admin-btn--primary" onClick={() => { setPage(1); load(); }}>Apply Filters</button>
        <button type="button" className="admin-btn" onClick={() => { setFilters({ location_id: '', visitor_type_id: '', company: '', status: '', source: '', security_status: '', compliance_status: '', registration_reference: '' }); setRange(defaultRange()); setPage(1); }}>Reset</button>
        {canExportCsv && <button type="button" className="admin-btn" disabled={exporting !== null} onClick={() => exportFile('csv')}>{exporting === 'csv' ? 'Preparing…' : 'Download CSV'}</button>}
        {canExportXlsx && <button type="button" className="admin-btn" disabled={exporting !== null} onClick={() => exportFile('xlsx')}>{exporting === 'xlsx' ? 'Preparing…' : 'Download Excel'}</button>}
      </div>

      {error && <p style={{ color: 'var(--color-danger)', fontSize: '0.875rem' }}>{error}</p>}
      <p style={{ fontSize: '0.875rem', marginBottom: '0.5rem' }}>Results: <strong>{total}</strong></p>

      {loading ? <LoadingState message="Loading reports…" /> : (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Reference</th>
                <th>Visitor</th>
                <th>Company</th>
                <th>Location</th>
                <th>Status</th>
                <th>Expected Arrival</th>
                <th>Expected Departure</th>
                <th>Actual Check-In</th>
                <th>Actual Check-Out</th>
                <th>Duration (min)</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? <tr><td colSpan={10}>No records for selected filters.</td></tr> : items.map((r, i) => (
                <tr key={r.registration_reference ?? i}>
                  <td>{r.registration_reference}</td>
                  <td>{r.visitor_name}</td>
                  <td>{r.company}</td>
                  <td>{r.location_name}</td>
                  <td>{r.status}</td>
                  <td>{r.scheduled_start ? new Date(r.scheduled_start).toLocaleString() : '—'}</td>
                  <td>{r.scheduled_end ? new Date(r.scheduled_end).toLocaleString() : '—'}</td>
                  <td>{r.checked_in_at ? new Date(r.checked_in_at).toLocaleString() : '—'}</td>
                  <td>{r.checked_out_at ? new Date(r.checked_out_at).toLocaleString() : '—'}</td>
                  <td>{r.visit_duration_minutes ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
        <button type="button" className="admin-btn" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</button>
        <span style={{ fontSize: '0.8125rem' }}>Page {page}</span>
        <button type="button" className="admin-btn" disabled={page * pageSize >= total} onClick={() => setPage((p) => p + 1)}>Next</button>
        <select value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}>
          <option value={25}>25</option>
          <option value={50}>50</option>
          <option value={100}>100</option>
        </select>
      </div>
    </div>
  );
}
