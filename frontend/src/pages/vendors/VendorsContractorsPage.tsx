import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../services/api';
import type { ComplianceReviewItem, ComplianceVisitDetail, VendorCompanyDetail, VendorCompanyItem } from '../../types';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import { useAuth } from '../../hooks/useAuth';
import { hasPermission } from '../../utils/permissions';
import { ComplianceDetailPanel } from './ComplianceDetailPanel';
import { ComplianceRequirementsPanel } from './ComplianceRequirementsPanel';
import { complianceClass, formatComplianceStatus, formatDateLabel } from './complianceUtils';
import '../../styles/admin-pages.css';

const MAIN_TABS = [
  { id: 'vendors', label: 'Vendors' },
  { id: 'visits', label: 'Contractor Visits' },
  { id: 'compliance', label: 'Compliance Review' },
  { id: 'requirements', label: 'Compliance Requirements' },
];

const COMPLIANCE_TABS = [
  { id: 'attention', label: 'Needs Attention' },
  { id: 'expiring', label: 'Expiring Soon' },
  { id: 'cleared', label: 'Cleared' },
];

export function VendorsContractorsPage() {
  const { user } = useAuth();
  const permissions = user?.permissions ?? [];
  const [tab, setTab] = useState('vendors');
  const [complianceTab, setComplianceTab] = useState('attention');
  const [vendors, setVendors] = useState<VendorCompanyItem[]>([]);
  const [visits, setVisits] = useState<ComplianceReviewItem[]>([]);
  const [reviews, setReviews] = useState<ComplianceReviewItem[]>([]);
  const [attentionCount, setAttentionCount] = useState(0);
  const [expiringCount, setExpiringCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [detail, setDetail] = useState<ComplianceVisitDetail | null>(null);
  const [vendorDetail, setVendorDetail] = useState<VendorCompanyDetail | null>(null);

  const canCreate = hasPermission(permissions, 'vendor_company.manage');
  const canManageRequirements = hasPermission(permissions, 'compliance.manage_requirements');
  const visibleTabs = MAIN_TABS.filter((t) => t.id !== 'requirements' || canManageRequirements);

  const load = useCallback(async () => {
    setError(null);
    try {
      if (tab === 'vendors') {
        const data = await api.vendorCompanies({ search: search || undefined, limit: 50 });
        setVendors(data.items);
      } else if (tab === 'visits') {
        const data = await api.contractorVisits({ search: search || undefined, limit: 50 });
        setVisits(data.items);
      } else if (tab === 'compliance') {
        const data = await api.complianceReviews({
          search: search || undefined,
          tab: complianceTab === 'attention' ? undefined : complianceTab,
          limit: 50,
        });
        setReviews(data.items);
        setAttentionCount(data.attention_count);
        setExpiringCount(data.expiring_count);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [tab, search, complianceTab]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  const openVisitDetail = async (visitId: number) => {
    try {
      const d = await api.complianceVisitDetail(visitId);
      setDetail(d);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load visit detail');
    }
  };

  const refreshDetail = async () => {
    if (!detail) return;
    const d = await api.complianceVisitDetail(detail.visit_id);
    setDetail(d);
    await load();
  };

  const openVendorDetail = async (id: number) => {
    try {
      const d = await api.vendorCompanyDetail(id);
      setVendorDetail(d);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load vendor');
    }
  };

  return (
    <div className="vms-page-shell">
      <header style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>Vendors & Contractors</h1>
          <p style={{ fontSize: '0.875rem', color: 'var(--color-slate-500)', margin: '0.25rem 0 0' }}>Vendor access and compliance operations</p>
        </div>
        {canCreate && (
          <Link to="/vendors-contractors/new-visit" className="admin-btn admin-btn--primary" style={{ textDecoration: 'none' }}>
            New Contractor Visit
          </Link>
        )}
      </header>

      <div className="admin-tabs">
        {visibleTabs.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`admin-tab ${tab === t.id ? 'admin-tab--active' : ''}`}
            onClick={() => { setTab(t.id); setLoading(true); }}
          >
            {t.id === 'compliance' && attentionCount ? `${t.label} (${attentionCount})` : t.label}
          </button>
        ))}
      </div>

      {tab !== 'requirements' && (
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
          <input type="search" placeholder="Search" value={search} onChange={(e) => setSearch(e.target.value)} style={{ minWidth: '220px' }} />
          <button type="button" className="admin-btn" onClick={() => { setLoading(true); load(); }}>Refresh</button>
        </div>
      )}

      {tab === 'compliance' && (
        <div className="admin-tabs" style={{ marginBottom: '1rem' }}>
          {COMPLIANCE_TABS.map((t) => {
            let label = t.label;
            if (t.id === 'attention' && attentionCount) label = `${t.label} (${attentionCount})`;
            if (t.id === 'expiring' && expiringCount) label = `${t.label} (${expiringCount})`;
            return (
              <button
                key={t.id}
                type="button"
                className={`admin-tab ${complianceTab === t.id ? 'admin-tab--active' : ''}`}
                onClick={() => { setComplianceTab(t.id); setLoading(true); }}
              >
                {label}
              </button>
            );
          })}
        </div>
      )}

      {loading && tab !== 'requirements' && <LoadingState message="Loading…" />}
      {error && <ErrorState title="Unable to load" message={error} action={{ label: 'Retry', onClick: () => { setLoading(true); load(); } }} />}

      {!loading && !error && tab === 'vendors' && (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr><th>Company</th><th>Contact</th><th>Locations</th><th>Status</th></tr>
            </thead>
            <tbody>
              {vendors.length === 0 ? (
                <tr><td colSpan={4}>No vendor companies found.</td></tr>
              ) : vendors.map((v) => (
                <tr key={v.id} onClick={() => openVendorDetail(v.id)} style={{ cursor: 'pointer' }}>
                  <td>{v.name}</td>
                  <td>{v.primary_contact_name ?? '—'}</td>
                  <td>{v.locations?.map((l) => l.name).join(', ') ?? '—'}</td>
                  <td>{v.is_active ? 'Active' : 'Inactive'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && !error && tab === 'visits' && (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr><th>Visitor</th><th>Vendor</th><th>Location</th><th>Compliance</th><th>Status</th></tr>
            </thead>
            <tbody>
              {visits.length === 0 ? (
                <tr><td colSpan={5}>No contractor visits found.</td></tr>
              ) : visits.map((v) => (
                <tr key={v.visit_id} onClick={() => openVisitDetail(v.visit_id)} style={{ cursor: 'pointer' }}>
                  <td>{v.visitor_name}</td>
                  <td>{v.vendor_company_name ?? '—'}</td>
                  <td>{v.site_name ?? '—'}</td>
                  <td><span className={complianceClass(v.compliance_status ?? '')}>{formatComplianceStatus(v.compliance_status ?? '—')}</span></td>
                  <td>{v.status ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && !error && tab === 'compliance' && (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr><th>Contractor</th><th>Vendor</th><th>Location</th><th>Issue</th><th>Status</th></tr>
            </thead>
            <tbody>
              {reviews.length === 0 ? (
                <tr><td colSpan={5}>No compliance reviews require attention.</td></tr>
              ) : reviews.map((r) => (
                <tr key={r.visit_id} onClick={() => openVisitDetail(r.visit_id)} style={{ cursor: 'pointer' }}>
                  <td>{r.visitor_name}</td>
                  <td>{r.vendor_company_name ?? '—'}</td>
                  <td>{r.site_name ?? '—'}</td>
                  <td>{r.issue ?? r.compliance_status}</td>
                  <td><span className={complianceClass(r.compliance_status ?? '')}>{formatComplianceStatus(r.compliance_status ?? '—')}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'requirements' && canManageRequirements && <ComplianceRequirementsPanel />}

      {detail && (
        <ComplianceDetailPanel
          detail={detail}
          permissions={permissions}
          onClose={() => setDetail(null)}
          onRefresh={refreshDetail}
        />
      )}

      {vendorDetail && (
        <div className="admin-detail-overlay" onClick={() => setVendorDetail(null)}>
          <div className="admin-detail-panel" onClick={(e) => e.stopPropagation()}>
            <button type="button" className="admin-btn" onClick={() => setVendorDetail(null)} style={{ marginBottom: '1rem' }}>Close</button>
            <h2>{vendorDetail.name}</h2>
            <div className="admin-detail-row"><div className="admin-detail-label">Contact</div><div>{vendorDetail.primary_contact_name ?? '—'}</div></div>
            <div className="admin-detail-row"><div className="admin-detail-label">Locations</div><div>{vendorDetail.locations?.map((l) => l.name).join(', ') ?? '—'}</div></div>
            <h3 style={{ fontSize: '0.9375rem', margin: '1rem 0 0.5rem' }}>Company Documents</h3>
            {vendorDetail.compliance_documents?.length ? vendorDetail.compliance_documents.map((g) => (
              <div key={g.requirement_id} style={{ fontSize: '0.8125rem', marginBottom: '0.5rem' }}>
                <strong>{g.requirement_name}</strong> — {g.current_status ?? 'Missing'}
                {g.valid_until && ` until ${formatDateLabel(g.valid_until)}`}
              </div>
            )) : <p style={{ fontSize: '0.875rem', color: 'var(--color-slate-500)' }}>No reusable company documents.</p>}
            <h3 style={{ fontSize: '0.9375rem', margin: '1rem 0 0.5rem' }}>Known Contractors</h3>
            {vendorDetail.contractors?.length ? (
              <ul style={{ fontSize: '0.8125rem', paddingLeft: '1.25rem' }}>
                {vendorDetail.contractors.map((c) => <li key={c.visitor_id}>{c.full_name} {c.trade_or_role ? `(${c.trade_or_role})` : ''}</li>)}
              </ul>
            ) : <p style={{ fontSize: '0.875rem', color: 'var(--color-slate-500)' }}>No linked contractors.</p>}
          </div>
        </div>
      )}
    </div>
  );
}
