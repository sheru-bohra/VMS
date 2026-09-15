import { useState } from 'react';
import { api } from '../../services/api';
import type { ComplianceVisitDetail } from '../../types';
import { hasPermission } from '../../utils/permissions';
import {
  ALLOWED_EXTENSIONS,
  complianceClass,
  formatComplianceStatus,
  formatDateLabel,
  MAX_UPLOAD_MB,
  parseComplianceSignals,
  REJECT_REASONS,
  usabilityClass,
  usabilityLabel,
  validateFile,
  type UploadTarget,
} from './complianceUtils';

type Props = {
  detail: ComplianceVisitDetail;
  permissions: string[];
  onClose: () => void;
  onRefresh: () => Promise<void>;
};

export function ComplianceDetailPanel({ detail, permissions, onClose, onRefresh }: Props) {
  const canUpload = hasPermission(permissions, 'compliance.verify');
  const canDownload = hasPermission(permissions, 'compliance.document.download');
  const [feedback, setFeedback] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [uploadTarget, setUploadTarget] = useState<UploadTarget | null>(null);
  const [verifyDocId, setVerifyDocId] = useState<number | null>(null);
  const [rejectDocId, setRejectDocId] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState('incorrect');
  const [rejectComment, setRejectComment] = useState('');
  const [uploading, setUploading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [validFrom, setValidFrom] = useState('');
  const [validUntil, setValidUntil] = useState('');

  const signals = parseComplianceSignals(detail.compliance);

  const runRefresh = async (message?: string) => {
    await onRefresh();
    if (message) setFeedback(message);
    setActionError(null);
  };

  const handleUpload = async () => {
    if (!uploadTarget || !file) return;
    const err = validateFile(file);
    if (err) {
      setActionError(err);
      return;
    }
    setUploading(true);
    setActionError(null);
    try {
      const fd = new FormData();
      fd.append('requirement_id', String(uploadTarget.requirementId));
      fd.append('file', file);
      fd.append('visit_id', String(uploadTarget.visitId));
      if (uploadTarget.vendorCompanyId) fd.append('vendor_company_id', String(uploadTarget.vendorCompanyId));
      if (uploadTarget.visitorId) fd.append('visitor_id', String(uploadTarget.visitorId));
      if (uploadTarget.supersedesId) fd.append('supersedes_id', String(uploadTarget.supersedesId));
      if (validFrom) fd.append('valid_from', new Date(validFrom).toISOString());
      if (validUntil) fd.append('valid_until', new Date(validUntil).toISOString());
      await api.uploadComplianceDocument(fd);
      setUploadTarget(null);
      setFile(null);
      setValidFrom('');
      setValidUntil('');
      await runRefresh('Document uploaded. Status: Pending Verification.');
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleVerify = async () => {
    if (!verifyDocId) return;
    setActionLoading(true);
    setActionError(null);
    try {
      await api.verifyComplianceDocument(verifyDocId, detail.visit_id);
      setVerifyDocId(null);
      await runRefresh('Document verified. Compliance re-evaluated.');
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Verification failed');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!rejectDocId) return;
    const comment = rejectReason === 'other'
      ? rejectComment.trim()
      : `${REJECT_REASONS.find((r) => r.id === rejectReason)?.label ?? rejectReason}`;
    if (!comment) {
      setActionError('Rejection comment is required.');
      return;
    }
    setActionLoading(true);
    setActionError(null);
    try {
      await api.rejectComplianceDocument(rejectDocId, comment, detail.visit_id);
      setRejectDocId(null);
      setRejectComment('');
      await runRefresh('Document rejected. Compliance re-evaluated.');
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Rejection failed');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDownload = async (docId: number, fileName: string) => {
    try {
      const blob = await api.downloadComplianceDocument(docId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Download failed');
    }
  };

  return (
    <div className="admin-detail-overlay" onClick={onClose}>
      <div className="admin-detail-panel" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '520px' }}>
        <button type="button" className="admin-btn" onClick={onClose} style={{ marginBottom: '1rem' }}>Close</button>
        <h2 style={{ fontSize: '1.125rem', margin: '0 0 0.25rem' }}>{detail.visitor_name}</h2>
        <p style={{ color: 'var(--color-slate-500)', fontSize: '0.875rem', margin: '0 0 1rem' }}>{detail.registration_reference}</p>

        <div className="admin-detail-row"><div className="admin-detail-label">Vendor</div><div>{detail.vendor_company_name ?? '—'}</div></div>
        <div className="admin-detail-row"><div className="admin-detail-label">Type</div><div>{detail.visitor_type ?? '—'}</div></div>
        <div className="admin-detail-row"><div className="admin-detail-label">Location</div><div>{detail.site_name ?? '—'}</div></div>
        <div className="admin-detail-row"><div className="admin-detail-label">Host</div><div>{detail.host_name ?? '—'}</div></div>
        <div className="admin-detail-row"><div className="admin-detail-label">Visit</div><div>{formatDateLabel(detail.scheduled_start)}</div></div>
        <div className="admin-detail-row"><div className="admin-detail-label">Work purpose</div><div>{detail.work_purpose ?? '—'}</div></div>
        <div className="admin-detail-row"><div className="admin-detail-label">PO / WO</div><div>{detail.po_work_order_reference ?? '—'}</div></div>
        <div className="admin-detail-row">
          <div className="admin-detail-label">Safety</div>
          <div>{detail.safety_acknowledged ? 'Acknowledged' : 'Not acknowledged'}</div>
        </div>

        <div style={{ marginTop: '1rem', padding: '0.75rem', background: 'var(--color-slate-50)', borderRadius: '6px' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-slate-500)', marginBottom: '0.35rem' }}>OVERALL COMPLIANCE</div>
          <span className={complianceClass(detail.compliance.compliance_status)}>
            {formatComplianceStatus(detail.compliance.compliance_status)}
          </span>
          {signals.length > 0 && (
            <ul style={{ margin: '0.75rem 0 0', paddingLeft: '1.25rem', fontSize: '0.8125rem' }}>
              {signals.map((s) => <li key={s}>{s}</li>)}
            </ul>
          )}
          {feedback && <p style={{ margin: '0.75rem 0 0', fontSize: '0.8125rem', color: 'var(--color-success)' }}>{feedback}</p>}
          {actionError && <p style={{ margin: '0.5rem 0 0', fontSize: '0.8125rem', color: 'var(--color-danger)' }}>{actionError}</p>}
        </div>

        <div style={{ marginTop: '1.25rem' }}>
          <div style={{ fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.5rem' }}>Required Documents</div>
          {detail.requirements.length === 0 ? (
            <p style={{ fontSize: '0.875rem', color: 'var(--color-slate-500)' }}>No document requirements apply.</p>
          ) : detail.requirements.map((req) => {
            const current = req.documents.find((d) => d.id === req.current_document_id);
            const history = req.documents.filter((d) => !d.is_current);
            return (
              <div key={req.requirement_id} style={{ borderTop: '1px solid var(--color-slate-200)', padding: '0.75rem 0' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', alignItems: 'flex-start' }}>
                  <div>
                    <div style={{ fontWeight: 500, fontSize: '0.875rem' }}>{req.requirement_name}</div>
                    <span className={usabilityClass(req.usability)} style={{ marginTop: '0.25rem', display: 'inline-block' }}>
                      {usabilityLabel(req.usability)}
                    </span>
                    {current?.valid_until && (
                      <div style={{ fontSize: '0.75rem', color: 'var(--color-slate-500)', marginTop: '0.25rem' }}>
                        Valid until {formatDateLabel(current.valid_until)}
                      </div>
                    )}
                    {req.usability === 'expiring' && detail.scheduled_start && (
                      <div style={{ fontSize: '0.75rem', marginTop: '0.25rem' }}>
                        Visit date: {formatDateLabel(detail.scheduled_start)}
                      </div>
                    )}
                  </div>
                  {canUpload && (req.usability === 'missing' || req.usability === 'expired' || req.usability === 'rejected' || !current) && (
                    <button
                      type="button"
                      className="admin-btn admin-btn--primary"
                      style={{ fontSize: '0.75rem' }}
                      onClick={() => setUploadTarget({
                        requirementId: req.requirement_id,
                        requirementName: req.requirement_name,
                        documentOwnerType: req.document_owner_type,
                        vendorCompanyId: req.document_owner_type === 'COMPANY' ? detail.vendor_company_id : undefined,
                        visitorId: req.document_owner_type === 'VISITOR' ? detail.visitor_id : undefined,
                        supersedesId: current?.id,
                        visitId: detail.visit_id,
                      })}
                    >
                      {current ? 'Renew' : 'Upload'}
                    </button>
                  )}
                </div>
                {current && (
                  <div style={{ marginTop: '0.5rem', fontSize: '0.8125rem' }}>
                    <strong>CURRENT:</strong> {current.file_name} — {current.status}
                    {canDownload && (
                      <button type="button" className="admin-btn" style={{ marginLeft: '0.5rem', fontSize: '0.75rem' }} onClick={() => handleDownload(current.id, current.file_name)}>
                        Download
                      </button>
                    )}
                    {canUpload && current.status === 'PENDING_VERIFICATION' && (
                      <>
                        <button type="button" className="admin-btn admin-btn--primary" style={{ marginLeft: '0.5rem', fontSize: '0.75rem' }} onClick={() => setVerifyDocId(current.id)}>Verify</button>
                        <button type="button" className="admin-btn admin-btn--danger" style={{ marginLeft: '0.25rem', fontSize: '0.75rem' }} onClick={() => setRejectDocId(current.id)}>Reject</button>
                      </>
                    )}
                  </div>
                )}
                {history.length > 0 && (
                  <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--color-slate-500)' }}>
                    Previous: {history.map((d) => `${d.file_name} (${d.status})`).join('; ')}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {uploadTarget && (
          <div style={{ marginTop: '1rem', border: '1px solid var(--color-slate-200)', padding: '1rem', borderRadius: '6px' }}>
            <h3 style={{ fontSize: '0.9375rem', margin: '0 0 0.75rem' }}>Upload Document</h3>
            <p style={{ fontSize: '0.8125rem', margin: '0 0 0.5rem' }}><strong>{uploadTarget.requirementName}</strong></p>
            <p style={{ fontSize: '0.75rem', color: 'var(--color-slate-500)', margin: '0 0 0.75rem' }}>
              Allowed: PDF, JPG, PNG — max {MAX_UPLOAD_MB} MB
            </p>
            <input type="file" accept={ALLOWED_EXTENSIONS.join(',')} onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            <div style={{ display: 'grid', gap: '0.5rem', marginTop: '0.75rem' }}>
              <label style={{ fontSize: '0.8125rem' }}>Valid from<input type="date" value={validFrom} onChange={(e) => setValidFrom(e.target.value)} style={{ width: '100%', marginTop: '0.25rem' }} /></label>
              <label style={{ fontSize: '0.8125rem' }}>Valid until<input type="date" value={validUntil} onChange={(e) => setValidUntil(e.target.value)} style={{ width: '100%', marginTop: '0.25rem' }} /></label>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
              <button type="button" className="admin-btn" onClick={() => { setUploadTarget(null); setFile(null); }}>Cancel</button>
              <button type="button" className="admin-btn admin-btn--primary" disabled={uploading || !file} onClick={handleUpload}>
                {uploading ? 'Uploading document…' : 'Upload Document'}
              </button>
            </div>
          </div>
        )}

        {verifyDocId && (
          <div style={{ marginTop: '1rem', border: '1px solid var(--color-slate-200)', padding: '1rem', borderRadius: '6px' }}>
            <p style={{ fontSize: '0.875rem', margin: '0 0 0.75rem' }}>Verify this compliance document?</p>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button type="button" className="admin-btn" onClick={() => setVerifyDocId(null)}>Cancel</button>
              <button type="button" className="admin-btn admin-btn--primary" disabled={actionLoading} onClick={handleVerify}>Verify</button>
            </div>
          </div>
        )}

        {rejectDocId && (
          <div style={{ marginTop: '1rem', border: '1px solid var(--color-slate-200)', padding: '1rem', borderRadius: '6px' }}>
            <p style={{ fontSize: '0.875rem', margin: '0 0 0.5rem' }}>Reject document</p>
            <select value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} style={{ width: '100%', marginBottom: '0.5rem' }}>
              {REJECT_REASONS.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
            </select>
            {rejectReason === 'other' && (
              <textarea rows={2} value={rejectComment} onChange={(e) => setRejectComment(e.target.value)} placeholder="Comment required" style={{ width: '100%', marginBottom: '0.5rem' }} />
            )}
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button type="button" className="admin-btn" onClick={() => setRejectDocId(null)}>Cancel</button>
              <button type="button" className="admin-btn admin-btn--danger" disabled={actionLoading} onClick={handleReject}>Reject</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
