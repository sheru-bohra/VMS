import { useCallback, useEffect, useState } from 'react';
import { api } from '../../services/api';
import type { ComplianceRequirementItem, Location, PublicVisitorType } from '../../types';
import { LoadingState, ErrorState } from '../../components/StatePanels';

export function ComplianceRequirementsPanel() {
  const [items, setItems] = useState<ComplianceRequirementItem[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [visitorTypes, setVisitorTypes] = useState<PublicVisitorType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    name: '',
    description: '',
    visitor_type_id: '',
    scope_type: 'GLOBAL',
    location_id: '',
    document_owner_type: 'VISITOR',
    document_required: true,
    validity_required: true,
    is_mandatory: true,
    expiry_warning_days: 30,
    safety_acknowledgement_required: false,
  });

  const load = useCallback(async () => {
    setError(null);
    try {
      const [reqs, locs, types] = await Promise.all([
        api.complianceRequirementsAdmin(true),
        api.locations(),
        api.visitorTypes(),
      ]);
      setItems(reqs);
      setLocations(locs);
      setVisitorTypes(types);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load requirements');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const submit = async () => {
    if (!form.name.trim()) {
      setFormError('Name is required.');
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      await api.createComplianceRequirement({
        name: form.name.trim(),
        description: form.description || undefined,
        visitor_type_id: form.visitor_type_id ? Number(form.visitor_type_id) : undefined,
        scope_type: form.scope_type,
        location_id: form.scope_type === 'LOCATION' && form.location_id ? Number(form.location_id) : undefined,
        document_owner_type: form.document_owner_type,
        document_required: form.document_required,
        validity_required: form.validity_required,
        is_mandatory: form.is_mandatory,
        expiry_warning_days: form.expiry_warning_days,
        safety_acknowledgement_required: form.safety_acknowledgement_required,
      });
      setShowForm(false);
      setForm({
        name: '', description: '', visitor_type_id: '', scope_type: 'GLOBAL', location_id: '',
        document_owner_type: 'VISITOR', document_required: true, validity_required: true,
        is_mandatory: true, expiry_warning_days: 30, safety_acknowledgement_required: false,
      });
      setLoading(true);
      await load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Unable to create requirement');
    } finally {
      setSubmitting(false);
    }
  };

  const deactivate = async (id: number) => {
    try {
      await api.deactivateComplianceRequirement(id);
      setLoading(true);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to deactivate');
    }
  };

  if (loading) return <LoadingState message="Loading requirements…" />;
  if (error) return <ErrorState title="Unable to load" message={error} action={{ label: 'Retry', onClick: () => { setLoading(true); load(); } }} />;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: 0 }}>Compliance Requirements</h2>
        <button type="button" className="admin-btn admin-btn--primary" onClick={() => setShowForm(true)}>Add Requirement</button>
      </div>

      {showForm && (
        <div style={{ border: '1px solid var(--color-slate-200)', padding: '1rem', borderRadius: '6px', marginBottom: '1rem' }}>
          <h3 style={{ fontSize: '0.9375rem', margin: '0 0 0.75rem' }}>Create Requirement</h3>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.8125rem' }}>Name *
            <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} style={{ width: '100%', marginTop: '0.25rem' }} />
          </label>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.8125rem' }}>Description
            <textarea value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} rows={2} style={{ width: '100%', marginTop: '0.25rem' }} />
          </label>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.8125rem' }}>Applies to visitor type
            <select value={form.visitor_type_id} onChange={(e) => setForm((f) => ({ ...f, visitor_type_id: e.target.value }))} style={{ width: '100%', marginTop: '0.25rem' }}>
              <option value="">All vendor types</option>
              {visitorTypes.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </label>
          <div style={{ marginBottom: '0.5rem', fontSize: '0.8125rem' }}>
            Scope
            <label style={{ display: 'block', marginTop: '0.25rem' }}>
              <input type="radio" checked={form.scope_type === 'GLOBAL'} onChange={() => setForm((f) => ({ ...f, scope_type: 'GLOBAL' }))} /> Global
            </label>
            <label style={{ display: 'block' }}>
              <input type="radio" checked={form.scope_type === 'LOCATION'} onChange={() => setForm((f) => ({ ...f, scope_type: 'LOCATION' }))} /> Location
            </label>
          </div>
          {form.scope_type === 'LOCATION' && (
            <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.8125rem' }}>Location
              <select value={form.location_id} onChange={(e) => setForm((f) => ({ ...f, location_id: e.target.value }))} style={{ width: '100%', marginTop: '0.25rem' }}>
                <option value="">Select location</option>
                {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
              </select>
            </label>
          )}
          <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.8125rem' }}>Document owner
            <select value={form.document_owner_type} onChange={(e) => setForm((f) => ({ ...f, document_owner_type: e.target.value }))} style={{ width: '100%', marginTop: '0.25rem' }}>
              <option value="VISITOR">Contractor / Visitor</option>
              <option value="COMPANY">Vendor Company</option>
            </select>
          </label>
          <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', fontSize: '0.8125rem', marginBottom: '0.35rem' }}>
            <input type="checkbox" checked={form.document_required} onChange={(e) => setForm((f) => ({ ...f, document_required: e.target.checked }))} /> Document required
          </label>
          <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', fontSize: '0.8125rem', marginBottom: '0.35rem' }}>
            <input type="checkbox" checked={form.validity_required} onChange={(e) => setForm((f) => ({ ...f, validity_required: e.target.checked }))} /> Validity required
          </label>
          <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', fontSize: '0.8125rem', marginBottom: '0.35rem' }}>
            <input type="checkbox" checked={form.is_mandatory} onChange={(e) => setForm((f) => ({ ...f, is_mandatory: e.target.checked }))} /> Mandatory
          </label>
          <label style={{ display: 'block', marginBottom: '0.75rem', fontSize: '0.8125rem' }}>Expiry warning (days)
            <input type="number" min={1} max={365} value={form.expiry_warning_days} onChange={(e) => setForm((f) => ({ ...f, expiry_warning_days: Number(e.target.value) }))} style={{ width: '100%', marginTop: '0.25rem' }} />
          </label>
          {formError && <p style={{ color: 'var(--color-danger)', fontSize: '0.8125rem' }}>{formError}</p>}
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button type="button" className="admin-btn" onClick={() => setShowForm(false)}>Cancel</button>
            <button type="button" className="admin-btn admin-btn--primary" disabled={submitting} onClick={submit}>Create Requirement</button>
          </div>
        </div>
      )}

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Requirement</th>
              <th>Scope</th>
              <th>Applies To</th>
              <th>Mandatory</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr><td colSpan={6}>No compliance requirements configured.</td></tr>
            ) : items.map((r) => (
              <tr key={r.id}>
                <td>{r.name}</td>
                <td>{r.scope_type === 'LOCATION' ? r.location_name ?? 'Location' : 'Global'}</td>
                <td>{r.visitor_type_name ?? 'All'} / {r.document_owner_type}</td>
                <td>{r.is_mandatory ? 'Yes' : 'No'}</td>
                <td>{r.is_active ? 'Active' : 'Inactive'}</td>
                <td>
                  {r.is_active && (
                    <button type="button" className="admin-btn" style={{ fontSize: '0.75rem' }} onClick={() => deactivate(r.id)}>Deactivate</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
