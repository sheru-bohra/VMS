import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../services/api';
import type { PublicHost, VendorCompanyDetail, VendorCompanyItem } from '../../types';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import { useAuth } from '../../hooks/useAuth';
import { formatDateLabel } from './complianceUtils';

export function CreateVendorVisitPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [vendors, setVendors] = useState<VendorCompanyItem[]>([]);
  const [hosts, setHosts] = useState<PublicHost[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [vendorDocs, setVendorDocs] = useState<VendorCompanyDetail | null>(null);

  const locationId = user?.assigned_locations?.[0]?.id;

  const [form, setForm] = useState({
    vendor_company_id: '',
    visitor_type: 'CONTRACTOR',
    full_name: '',
    mobile: '',
    email: '',
    host_id: '',
    work_purpose: '',
    po_work_order_reference: '',
    visit_date: '',
    arrival_time: '10:00',
    expected_duration_minutes: 60,
    safety_acknowledged: false,
  });

  useEffect(() => {
    (async () => {
      try {
        const v = await api.vendorCompanies({ limit: 100 });
        setVendors(v.items);
        if (locationId) {
          const h = await api.locationHosts(locationId);
          setHosts(h);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load form data');
      } finally {
        setLoading(false);
      }
    })();
  }, [locationId]);

  useEffect(() => {
    if (!form.vendor_company_id) {
      setVendorDocs(null);
      return;
    }
    api.vendorCompanyDetail(Number(form.vendor_company_id))
      .then(setVendorDocs)
      .catch(() => setVendorDocs(null));
  }, [form.vendor_company_id]);

  const submit = async () => {
    if (!locationId) {
      setSubmitError('No assigned location.');
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      await api.createVendorVisit({
        location_id: locationId,
        visitor_type: form.visitor_type,
        vendor_company_id: Number(form.vendor_company_id),
        full_name: form.full_name,
        mobile: form.mobile,
        email: form.email,
        host_id: Number(form.host_id),
        work_purpose: form.work_purpose,
        visit_date: form.visit_date,
        arrival_time: form.arrival_time,
        expected_duration_minutes: form.expected_duration_minutes,
        safety_acknowledged: form.safety_acknowledged,
        po_work_order_reference: form.po_work_order_reference || undefined,
      });
      navigate('/vendors-contractors');
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Unable to create visit');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <LoadingState message="Loading form…" />;
  if (error) return <ErrorState title="Unable to load" message={error} />;

  return (
    <div className="vms-page-shell">
      <h1 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '1rem' }}>New Contractor Visit</h1>
      <div style={{ maxWidth: '520px' }}>
        <label style={{ display: 'block', marginBottom: '0.75rem' }}>
          Vendor Company *
          <select value={form.vendor_company_id} onChange={(e) => setForm((f) => ({ ...f, vendor_company_id: e.target.value }))} style={{ width: '100%', marginTop: '0.25rem' }}>
            <option value="">Select vendor</option>
            {vendors.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
          </select>
        </label>
        {vendorDocs?.compliance_documents && vendorDocs.compliance_documents.length > 0 && (
          <div style={{ marginBottom: '0.75rem', padding: '0.75rem', background: 'var(--color-slate-50)', borderRadius: '6px', fontSize: '0.8125rem' }}>
            <strong>Existing company compliance</strong>
            {vendorDocs.compliance_documents.map((d) => (
              <div key={d.requirement_id} style={{ marginTop: '0.35rem' }}>
                {d.requirement_name}: {d.current_status ?? 'Missing'}
                {d.valid_until && d.current_status === 'VALID' ? ` — valid until ${formatDateLabel(d.valid_until)}` : ''}
              </div>
            ))}
          </div>
        )}
        <label style={{ display: 'block', marginBottom: '0.75rem' }}>
          Visitor Type
          <select value={form.visitor_type} onChange={(e) => setForm((f) => ({ ...f, visitor_type: e.target.value }))} style={{ width: '100%', marginTop: '0.25rem' }}>
            <option value="CONTRACTOR">Contractor</option>
            <option value="VENDOR">Vendor</option>
            <option value="SERVICE">Service / Maintenance</option>
          </select>
        </label>
        <label style={{ display: 'block', marginBottom: '0.75rem' }}>Full name *<input value={form.full_name} onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))} style={{ width: '100%', marginTop: '0.25rem' }} /></label>
        <label style={{ display: 'block', marginBottom: '0.75rem' }}>Mobile *<input value={form.mobile} onChange={(e) => setForm((f) => ({ ...f, mobile: e.target.value }))} style={{ width: '100%', marginTop: '0.25rem' }} /></label>
        <label style={{ display: 'block', marginBottom: '0.75rem' }}>Email *<input value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} style={{ width: '100%', marginTop: '0.25rem' }} /></label>
        <label style={{ display: 'block', marginBottom: '0.75rem' }}>
          Host *
          <select value={form.host_id} onChange={(e) => setForm((f) => ({ ...f, host_id: e.target.value }))} style={{ width: '100%', marginTop: '0.25rem' }}>
            <option value="">Select host</option>
            {hosts.map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
          </select>
        </label>
        <label style={{ display: 'block', marginBottom: '0.75rem' }}>Work purpose *<textarea value={form.work_purpose} onChange={(e) => setForm((f) => ({ ...f, work_purpose: e.target.value }))} rows={2} style={{ width: '100%', marginTop: '0.25rem' }} /></label>
        <label style={{ display: 'block', marginBottom: '0.75rem' }}>PO / Work Order<input value={form.po_work_order_reference} onChange={(e) => setForm((f) => ({ ...f, po_work_order_reference: e.target.value }))} style={{ width: '100%', marginTop: '0.25rem' }} /></label>
        <label style={{ display: 'block', marginBottom: '0.75rem' }}>Visit date *<input type="date" value={form.visit_date} onChange={(e) => setForm((f) => ({ ...f, visit_date: e.target.value }))} style={{ width: '100%', marginTop: '0.25rem' }} /></label>
        <label style={{ display: 'block', marginBottom: '0.75rem' }}>Arrival time<input type="time" value={form.arrival_time} onChange={(e) => setForm((f) => ({ ...f, arrival_time: e.target.value }))} style={{ width: '100%', marginTop: '0.25rem' }} /></label>
        <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '1rem' }}>
          <input type="checkbox" checked={form.safety_acknowledged} onChange={(e) => setForm((f) => ({ ...f, safety_acknowledged: e.target.checked }))} />
          I confirm site safety requirements are understood
        </label>
        {submitError && <p style={{ color: 'var(--color-danger)', fontSize: '0.875rem' }}>{submitError}</p>}
        <button type="button" className="admin-btn admin-btn--primary" disabled={submitting} onClick={submit}>Create Visit</button>
      </div>
    </div>
  );
}
