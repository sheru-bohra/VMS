import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, ApiClientError } from '../../services/api';
import type { InvitationItem, Location, PublicHost, PublicVisitorType, VendorCompanyItem } from '../../types';
import { LoadingState } from '../../components/StatePanels';
import { PageHeader } from '../../components/shell/PageHeader';
import { PolicyModal } from '../../components/visit/PolicyModal';
import { PhotoCapture } from '../../components/register-visitor/PhotoCapture';
import { IdUploadPanel } from '../../components/register-visitor/IdUploadPanel';
import { useVisitorPhoto } from '../../components/register-visitor/useVisitorPhoto';
import { RegistrationStepper } from '../../components/register-visitor/RegistrationStepper';
import { SignaturePad } from '../../components/register-visitor/SignaturePad';
import { StaffHostSearch } from '../../components/register-visitor/StaffHostSearch';
import { useAuth } from '../../hooks/useAuth';
import { useOperationalLocations } from '../../hooks/useOperationalLocations';
import { usePreferredLocationId } from '../../hooks/usePreferredLocation';
import { triggerOperationalRefresh } from '../../utils/operationalRefreshEvents';
import {
  currentTimeInTimezone,
  getRegisterVisitorPolicy,
  locationTimezone,
  sanitizeMobileInput,
} from '../../utils/registerVisitorPolicy';
import {
  stepCompletion,
  validateRegisterVisitorForm,
  type RegisterVisitorFormState,
} from '../../utils/registerVisitorValidation';
import '../../styles/admin-pages.css';
import '../../styles/registration.css';
import '../../styles/register-visitor.css';

const STEPS = [
  { id: 1, label: 'Personal' },
  { id: 2, label: 'ID & Compliance' },
  { id: 3, label: 'Visit Details' },
  { id: 4, label: 'Review & Submit' },
];

const GOVT_ID_TYPES = [
  { value: '', label: '— Select —' },
  { value: 'PASSPORT', label: 'Passport' },
  { value: 'DRIVING_LICENSE', label: 'Driving License' },
  { value: 'NATIONAL_ID', label: 'National ID' },
  { value: 'COMPANY_ID', label: 'Company ID' },
  { value: 'OTHER', label: 'Other' },
];

const VEHICLE_TYPES = [
  { value: '', label: '— None —' },
  { value: 'CAR', label: 'Car' },
  { value: 'TWO_WHEELER', label: 'Two Wheeler' },
  { value: 'SUV', label: 'SUV' },
  { value: 'OTHER', label: 'Other' },
];

const PURPOSE_OPTIONS = [
  'Business Meeting',
  'Interview',
  'Delivery',
  'Maintenance',
  'Training',
  'Audit',
  'Other',
];

const ASSET_OPTIONS = [
  { key: 'laptop', label: 'Laptop' },
  { key: 'mobile', label: 'Mobile' },
  { key: 'camera', label: 'Camera' },
  { key: 'toolkit', label: 'Toolkit' },
  { key: 'hard_disk', label: 'Hard Disk' },
  { key: 'samples', label: 'Samples' },
  { key: 'company_equipment', label: 'Company Equipment' },
  { key: 'other', label: 'Other' },
];

function dataUrlToFile(dataUrl: string, name: string): File {
  const [header, data] = dataUrl.split(',');
  const mime = header.match(/:(.*?);/)?.[1] ?? 'image/png';
  const binary = atob(data);
  const arr = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) arr[i] = binary.charCodeAt(i);
  return new File([arr], name, { type: mime });
}

function todayIso(): string {
  const d = new Date();
  return d.toISOString().slice(0, 10);
}

function formatTimeLabel(value: string): string {
  if (!value) return '—';
  const [h, m] = value.split(':');
  if (!h || !m) return value;
  const hour = Number(h);
  const ampm = hour >= 12 ? 'PM' : 'AM';
  const displayHour = hour % 12 === 0 ? 12 : hour % 12;
  return `${displayHour}:${m} ${ampm}`;
}

function formatSubmitError(err: unknown): string {
  if (err instanceof ApiClientError) {
    if (err.code === 'internal_error') {
      return err.requestId
        ? `An unexpected error occurred. Reference: ${err.requestId}`
        : 'An unexpected error occurred.';
    }
    return err.message;
  }
  return err instanceof Error ? err.message : 'Registration failed';
}

function resolveVendorCompanyId(
  company: string,
  vendors: VendorCompanyItem[],
): number | undefined {
  const trimmed = company.trim().toLowerCase();
  if (!trimmed) return undefined;
  return vendors.find((v) => v.name.trim().toLowerCase() === trimmed)?.id;
}

export function RegisterVisitorPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const locations = useOperationalLocations(user);
  const preferredLocationId = usePreferredLocationId(user);

  const [visitorTypes, setVisitorTypes] = useState<PublicVisitorType[]>([]);
  const [vendors, setVendors] = useState<VendorCompanyItem[]>([]);
  const [activeStep, setActiveStep] = useState(1);
  const [policyOpen, setPolicyOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [success, setSuccess] = useState<InvitationItem | null>(null);
  const [showValidationSummary, setShowValidationSummary] = useState(false);

  const [fullName, setFullName] = useState('');
  const [mobile, setMobile] = useState('');
  const [email, setEmail] = useState('');
  const [company, setCompany] = useState('');
  const [visitorType, setVisitorType] = useState('');
  const [locationId, setLocationId] = useState<number | ''>('');
  const [address, setAddress] = useState('');
  const {
    photo,
    setLocalPhoto,
    markStaging,
    markStaged,
    markError,
    clearPhoto,
  } = useVisitorPhoto();
  const photoMediaIdRef = useRef<number | null>(null);
  photoMediaIdRef.current = photo.mediaId;

  const [signatureData, setSignatureData] = useState<string | null>(null);

  const [govtIdType, setGovtIdType] = useState('');
  const [govtIdNumber, setGovtIdNumber] = useState('');
  const [idFile, setIdFile] = useState<File | null>(null);
  const [idFileName, setIdFileName] = useState('');
  const [ndaSigned, setNdaSigned] = useState(false);
  const [ppeRequired, setPpeRequired] = useState(false);
  const [safetyInduction, setSafetyInduction] = useState(false);
  const [policyAccepted, setPolicyAccepted] = useState(false);

  const [purpose, setPurpose] = useState('');
  const [visitDate, setVisitDate] = useState(todayIso());
  const [arrivalTime, setArrivalTime] = useState('');
  const [departureTime, setDepartureTime] = useState('');
  const [hostId, setHostId] = useState<number | ''>('');
  const [hostDisplay, setHostDisplay] = useState<PublicHost | null>(null);
  const [vehicleNumber, setVehicleNumber] = useState('');
  const [vehicleType, setVehicleType] = useState('');
  const [notes, setNotes] = useState('');
  const [assets, setAssets] = useState<Set<string>>(new Set());
  const [assetsOther, setAssetsOther] = useState('');
  const [poReference, setPoReference] = useState('');
  const [workPurpose, setWorkPurpose] = useState('');

  const sectionRefs = useRef<Record<number, HTMLElement | null>>({});
  const arrivalTimeTouchedRef = useRef(false);
  const locationDefaultAppliedRef = useRef(false);
  const submitLockRef = useRef(false);
  const prevVisitorTypeRef = useRef('');

  const selectedVisitorType = visitorTypes.find((t) => t.code === visitorType);
  const policy = useMemo(
    () => getRegisterVisitorPolicy(visitorType, selectedVisitorType),
    [visitorType, selectedVisitorType],
  );

  const selectedLocation = locations.find((l: Location) => l.id === locationId);
  const locationLocked = locations.length === 1;

  const vendorCompanyId = useMemo(
    () => (policy.requiresVendorMatch ? resolveVendorCompanyId(company, vendors) : undefined),
    [policy.requiresVendorMatch, company, vendors],
  );

  const formState: RegisterVisitorFormState = useMemo(
    () => ({
      fullName,
      mobile,
      email,
      company,
      visitorType,
      locationId,
      address,
      signatureData,
      govtIdType,
      govtIdNumber,
      policyAccepted,
      safetyInduction,
      purpose,
      visitDate,
      arrivalTime,
      departureTime,
      hostId,
      poReference,
      workPurpose,
      photoStaging: photo.status === 'staging',
    }),
    [
      fullName, mobile, email, company, visitorType, locationId, address,
      signatureData, govtIdType, govtIdNumber, policyAccepted, safetyInduction,
      purpose, visitDate, arrivalTime, departureTime, hostId, poReference,
      workPurpose, photo.status,
    ],
  );

  const validationIssues = useMemo(
    () => validateRegisterVisitorForm(formState, selectedVisitorType),
    [formState, selectedVisitorType],
  );

  const completedSteps = useMemo(() => {
    const flags = stepCompletion(formState, selectedVisitorType);
    return STEPS.filter((_, i) => flags[i]).map((s) => s.id);
  }, [formState, selectedVisitorType]);

  const canSubmit = validationIssues.length === 0 && !submitting;

  useEffect(() => {
    api.visitorTypes().then(setVisitorTypes).catch(() => {});
  }, []);

  useEffect(() => {
    if (locations.length === 0 || locationDefaultAppliedRef.current) return;
    const preferred =
      preferredLocationId && locations.some((l) => l.id === preferredLocationId)
        ? preferredLocationId
        : locations[0]?.id;
    if (preferred) {
      setLocationId(preferred);
      locationDefaultAppliedRef.current = true;
    }
  }, [locations, preferredLocationId]);

  useEffect(() => {
    if (!locationId) {
      setVendors([]);
      return;
    }
    api.vendorCompanies({ location_id: Number(locationId), limit: 100 })
      .then((r) => setVendors(r.items))
      .catch(() => setVendors([]));
  }, [locationId]);

  useEffect(() => {
    if (!arrivalTimeTouchedRef.current && selectedLocation) {
      setArrivalTime(currentTimeInTimezone(locationTimezone(selectedLocation)));
    }
  }, [locationId, selectedLocation]);

  useEffect(() => {
    if (prevVisitorTypeRef.current === visitorType) return;
    prevVisitorTypeRef.current = visitorType;
    const nextPolicy = getRegisterVisitorPolicy(visitorType, selectedVisitorType);
    if (!nextPolicy.showGovtIdSection) {
      setGovtIdType('');
      setGovtIdNumber('');
      setIdFile(null);
      setIdFileName('');
    }
    if (!nextPolicy.showSignature) setSignatureData(null);
    if (!nextPolicy.showPoWorkOrder) setPoReference('');
    if (!nextPolicy.showWorkPurpose) setWorkPurpose('');
    if (!nextPolicy.showPpe) setPpeRequired(false);
    if (!nextPolicy.showSafetyInduction) setSafetyInduction(false);
    if (!nextPolicy.showNda) setNdaSigned(false);
  }, [visitorType, selectedVisitorType]);

  useEffect(() => {
    const observers: IntersectionObserver[] = [];
    STEPS.forEach((step) => {
      const el = sectionRefs.current[step.id];
      if (!el) return;
      const obs = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) setActiveStep(step.id);
          });
        },
        { rootMargin: '-20% 0px -55% 0px', threshold: 0 },
      );
      obs.observe(el);
      observers.push(obs);
    });
    return () => observers.forEach((o) => o.disconnect());
  }, [success, visitorType]);

  const onHostSelect = useCallback((host: PublicHost | null) => {
    setHostDisplay(host);
    setHostId(host?.id ?? '');
  }, []);

  useEffect(() => {
    if (!locationId || !hostId) return;
    api.locationHosts(Number(locationId))
      .then((hosts) => {
        const stillValid = hosts.some((h) => h.id === hostId);
        if (!stillValid) onHostSelect(null);
      })
      .catch(() => onHostSelect(null));
  }, [locationId, hostId, onHostSelect]);

  const handleLocationChange = (nextId: number | '') => {
    setLocationId(nextId);
    if (!arrivalTimeTouchedRef.current && nextId) {
      const loc = locations.find((l) => l.id === nextId);
      if (loc) {
        setArrivalTime(currentTimeInTimezone(locationTimezone(loc)));
      }
    }
  };

  const hasUnsavedData = useMemo(
    () =>
      fullName.trim() ||
      mobile.trim() ||
      email.trim() ||
      company.trim() ||
      purpose.trim() ||
      hostId,
    [fullName, mobile, email, company, purpose, hostId],
  );

  const handleBack = () => {
    if (hasUnsavedData && !success) {
      const ok = window.confirm('Discard unsaved registration?');
      if (!ok) return;
    }
    navigate('/dashboard');
  };

  const scrollToField = (fieldId?: string, step?: number) => {
    if (fieldId) {
      const el = document.getElementById(fieldId);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        if (el instanceof HTMLInputElement || el instanceof HTMLSelectElement || el instanceof HTMLTextAreaElement) {
          el.focus();
        }
        return;
      }
    }
    if (step) scrollToStep(step);
  };

  const scrollToStep = (stepId: number) => {
    sectionRefs.current[stepId]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    setActiveStep(stepId);
  };

  const stagePhotoFile = useCallback(
    async (file: File, source: 'upload' | 'webcam'): Promise<boolean> => {
      markStaging();
      try {
        const prevId = photoMediaIdRef.current;
        if (prevId) {
          await api.deleteVisitorPhoto(prevId).catch(() => undefined);
        }
        const res = await api.stageVisitorPhoto(file, {
          fullName: fullName.trim() || undefined,
          source,
          locationId: locationId ? Number(locationId) : undefined,
        });
        setLocalPhoto(file, source);
        markStaged(res.media_id, res.stored_filename);
        return true;
      } catch (err) {
        markError(err instanceof Error ? err.message : 'Unable to save photo');
        return false;
      }
    },
    [fullName, locationId, markStaging, markStaged, markError, setLocalPhoto],
  );

  const handleLocalPhoto = useCallback(
    async (file: File, source: 'upload' | 'webcam') => stagePhotoFile(file, source),
    [stagePhotoFile],
  );

  const handleClearPhoto = useCallback(async () => {
    const id = photoMediaIdRef.current;
    if (id) {
      await api.deleteVisitorPhoto(id).catch(() => undefined);
    }
    clearPhoto();
  }, [clearPhoto]);

  const toggleAsset = (key: string) => {
    setAssets((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const uploadAttachments = async () => {
    let signatureKey: string | undefined;
    let idKey: string | undefined;
    if (policy.showSignature && signatureData) {
      const file = dataUrlToFile(signatureData, 'signature.png');
      const res = await api.uploadRegistrationAttachment('signature', file);
      signatureKey = res.storage_key;
    }
    if (policy.showGovtIdSection && idFile) {
      const res = await api.uploadRegistrationAttachment('id_image', idFile);
      idKey = res.storage_key;
    }
    return { signatureKey, idKey };
  };

  const submit = async () => {
    if (submitLockRef.current) return;

    if (validationIssues.length > 0) {
      setShowValidationSummary(true);
      const first = validationIssues[0];
      scrollToField(first.fieldId, first.step);
      return;
    }

    if (!locationId) return;

    submitLockRef.current = true;
    setSubmitting(true);
    setSubmitError(null);
    setShowValidationSummary(false);

    try {
      const { signatureKey, idKey } = await uploadAttachments();

      const payload: Record<string, unknown> = {
        location_id: Number(locationId),
        visitor_type: visitorType,
        full_name: fullName.trim(),
        mobile: mobile.trim(),
        email: email.trim() || undefined,
        company: company.trim() || undefined,
        visit_date: visitDate,
        arrival_time: arrivalTime,
        departure_time: departureTime,
        expected_duration_minutes: 60,
        purpose: purpose.trim(),
        notes: notes.trim() || undefined,
        policy_accepted: policyAccepted,
        address: address.trim() || undefined,
        photo_media_id: photo.mediaId ?? undefined,
        vehicle_number: vehicleNumber.trim() || undefined,
        vehicle_type: vehicleType || undefined,
        assets: assets.size > 0 ? Array.from(assets) : undefined,
        assets_other: assets.has('other') ? assetsOther.trim() : undefined,
      };

      if (hostId) payload.host_id = Number(hostId);

      if (policy.showPoWorkOrder && poReference.trim()) {
        payload.po_work_order_reference = poReference.trim();
      }
      if (policy.showWorkPurpose && workPurpose.trim()) {
        payload.work_purpose = workPurpose.trim();
      }
      if (policy.showGovtIdSection) {
        payload.govt_id_type = govtIdType || undefined;
        payload.govt_id_number = govtIdNumber.trim() || undefined;
        payload.id_image_storage_key = idKey;
      }
      if (policy.showSignature) {
        payload.signature_storage_key = signatureKey;
      }
      if (policy.showNda) payload.nda_signed = ndaSigned;
      if (policy.showPpe) payload.ppe_required = ppeRequired;
      if (policy.showSafetyInduction) {
        payload.safety_induction_completed = safetyInduction;
        payload.safety_acknowledged = safetyInduction;
      }
      if (vendorCompanyId) payload.vendor_company_id = vendorCompanyId;

      const result = await api.createInvitation(payload);
      setSuccess(result);
      triggerOperationalRefresh();
    } catch (err) {
      setSubmitError(formatSubmitError(err));
      submitLockRef.current = false;
    } finally {
      setSubmitting(false);
    }
  };

  if (!user) return <LoadingState message="Loading…" />;

  if (success) {
    return (
      <div className="rv-page vms-page-shell">
        <PageHeader
          title="Register Visitor"
          subtitle="Registration complete"
          icon="user-round-plus"
          iconTone="violet"
        />
        <div className="rv-section-card rv-success-card">
          <h2>Registration successful</h2>
          <p><strong>Reference:</strong> {success.registration_reference ?? '—'}</p>
          <p><strong>Visitor:</strong> {success.visitor_name}</p>
          <p><strong>Location:</strong> {success.site_name}</p>
          <p><strong>Status:</strong> {success.status}</p>
          <p className="rv-submit-hint">
            {success.status === 'PENDING_APPROVAL'
              ? 'Awaiting approval before invitation QR is issued.'
              : 'Next step depends on your workflow configuration.'}
          </p>
          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center', marginTop: '1.5rem', flexWrap: 'wrap' }}>
            <Link to="/invitations" className="admin-btn admin-btn--outline">View Invitations</Link>
            <button type="button" className="admin-btn admin-btn--primary" onClick={() => window.location.reload()}>
              Create Another Visitor
            </button>
            <Link to="/dashboard" className="admin-btn admin-btn--outline">Back to Dashboard</Link>
          </div>
        </div>
      </div>
    );
  }

  const locationLabel = selectedLocation?.name ?? '—';

  const reviewFields: { label: string; value: string; show: boolean }[] = [
    { label: 'Full Name', value: fullName.trim() || '—', show: true },
    { label: 'Mobile', value: mobile.trim() || '—', show: true },
    { label: 'Email', value: email.trim() || '—', show: Boolean(email.trim()) },
    { label: 'Company', value: company.trim() || '—', show: policy.showCompany && Boolean(company.trim()) },
    { label: 'Visitor Type', value: selectedVisitorType?.name ?? '—', show: true },
    { label: 'Location', value: locationLabel, show: true },
    { label: 'Purpose', value: purpose.trim() || '—', show: true },
    { label: 'Visit Date', value: visitDate || '—', show: true },
    { label: 'Host', value: hostDisplay?.name ?? '—', show: Boolean(hostDisplay?.name) },
    { label: 'PO / Work Order', value: poReference.trim() || '—', show: policy.showPoWorkOrder && Boolean(poReference.trim()) },
    { label: 'Work Purpose', value: workPurpose.trim() || '—', show: policy.showWorkPurpose && Boolean(workPurpose.trim()) },
    { label: 'Govt ID', value: govtIdNumber.trim() ? `${govtIdType || 'ID'}: ${govtIdNumber.trim()}` : '—', show: policy.showGovtIdSection && Boolean(govtIdNumber.trim()) },
    { label: 'Vehicle', value: vehicleNumber.trim() || vehicleType || '—', show: Boolean(vehicleNumber.trim() || vehicleType) },
    { label: 'Policy Accepted', value: policyAccepted ? 'Yes' : 'Not accepted', show: true },
  ];

  return (
    <div className="rv-page vms-page-shell">
      <PageHeader
        title="Register Visitor"
        subtitle="Complete all sections and submit"
        icon="user-round-plus"
        iconTone="violet"
        actions={
          <button type="button" className="admin-btn admin-btn--outline rv-back-btn" onClick={handleBack}>
            ← Back
          </button>
        }
      />

      <RegistrationStepper
        steps={STEPS}
        activeStep={activeStep}
        completedSteps={completedSteps}
        onStepClick={scrollToStep}
      />

      <form
        className="registration-form"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <section
          id="step-1"
          ref={(el) => { sectionRefs.current[1] = el; }}
          className="rv-section-card"
        >
          <h2 className="rv-section-title">Step 1 — Personal Details</h2>
          <div className="rv-grid">
            <div className="reg-form-field">
              <label className="reg-form-label" htmlFor="field-fullName">Full Name *</label>
              <input
                id="field-fullName"
                className="reg-form-input"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Enter full name"
              />
            </div>
            <div className="reg-form-field">
              <label className="reg-form-label" htmlFor="field-mobile">Mobile *</label>
              <input
                id="field-mobile"
                className="reg-form-input"
                inputMode="numeric"
                value={mobile}
                onChange={(e) => setMobile(sanitizeMobileInput(e.target.value))}
                placeholder="10-digit mobile"
                maxLength={10}
              />
            </div>
            <div className="reg-form-field">
              <label className="reg-form-label" htmlFor="field-email">
                Email{policy.emailRequired ? ' *' : ''}
              </label>
              <input
                id="field-email"
                type="email"
                className="reg-form-input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="visitor@company.com"
              />
            </div>
            {policy.showCompany && (
              <div className="reg-form-field">
                <label className="reg-form-label" htmlFor="field-company">
                  Company Name{policy.companyRequired ? ' *' : ''}
                </label>
                <input
                  id="field-company"
                  className="reg-form-input"
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  placeholder="Company / Organization"
                />
              </div>
            )}
            <div className="reg-form-field">
              <label className="reg-form-label" htmlFor="field-visitorType">Visitor Type *</label>
              <select
                id="field-visitorType"
                className="reg-form-select"
                value={visitorType}
                onChange={(e) => setVisitorType(e.target.value)}
              >
                <option value="">— Select —</option>
                {visitorTypes.map((t) => (
                  <option key={t.code} value={t.code}>{t.name}</option>
                ))}
              </select>
            </div>
            <div className="reg-form-field">
              <label className="reg-form-label" htmlFor="field-location">Location *</label>
              <select
                id="field-location"
                className="reg-form-select"
                value={locationId}
                disabled={locationLocked}
                onChange={(e) => handleLocationChange(e.target.value ? Number(e.target.value) : '')}
              >
                <option value="">— Select —</option>
                {locations.map((l) => (
                  <option key={l.id} value={l.id}>{l.name}</option>
                ))}
              </select>
            </div>
            <div className="reg-form-field rv-grid--full">
              <label className="reg-form-label" htmlFor="field-address">Address</label>
              <textarea
                id="field-address"
                className="reg-form-textarea"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder="Full address…"
                rows={3}
              />
            </div>
            <div className={`rv-grid--full rv-media-row ${policy.showSignature ? '' : 'rv-media-row--photo-only'}`}>
              <div className="reg-form-field rv-media-col" id="field-photo">
                <label className="reg-form-label">Photo</label>
                <PhotoCapture
                  photo={photo}
                  fullName={fullName}
                  onLocalPhoto={handleLocalPhoto}
                  onClear={handleClearPhoto}
                />
              </div>
            </div>
          </div>
        </section>

        <section
          id="step-2"
          ref={(el) => { sectionRefs.current[2] = el; }}
          className="rv-section-card"
        >
          <h2 className="rv-section-title">Step 2 — Identity & Compliance</h2>

          {policy.idStepInfoMessage && !policy.showGovtIdSection && (
            <p className="rv-id-info">{policy.idStepInfoMessage}</p>
          )}

          {policy.showGovtIdSection && (
            <div className="rv-grid">
              <div className="reg-form-field">
                <label className="reg-form-label" htmlFor="field-govtIdType">Govt ID Type *</label>
                <select
                  id="field-govtIdType"
                  className="reg-form-select"
                  value={govtIdType}
                  onChange={(e) => setGovtIdType(e.target.value)}
                >
                  {GOVT_ID_TYPES.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>
              <div className="reg-form-field rv-grid--full">
                <div className="rv-id-panel-wrap">
                  <IdUploadPanel
                    fileName={idFileName}
                    onFileSelect={(f) => {
                      setIdFile(f);
                      setIdFileName(f?.name ?? '');
                    }}
                  />
                </div>
              </div>
              <div className="reg-form-field">
                <label className="reg-form-label" htmlFor="field-govtIdNumber">Govt ID Number *</label>
                <input
                  id="field-govtIdNumber"
                  className="reg-form-input"
                  value={govtIdNumber}
                  onChange={(e) => setGovtIdNumber(e.target.value)}
                  placeholder="ID number"
                />
              </div>
            </div>
          )}

          {policy.showSignature && (
            <div className="rv-grid" style={{ marginTop: '1rem' }}>
              <div className="reg-form-field rv-grid--full" id="field-signature">
                <label className="reg-form-label">Signature *</label>
                <SignaturePad onChange={setSignatureData} />
              </div>
            </div>
          )}

          <div style={{ marginTop: '1rem' }}>
            {policy.showNda && (
              <div className="rv-toggle-row">
                <span>NDA Signed</span>
                <input type="checkbox" checked={ndaSigned} onChange={(e) => setNdaSigned(e.target.checked)} aria-label="NDA Signed" />
              </div>
            )}
            {policy.showPpe && (
              <div className="rv-toggle-row">
                <span>PPE Required</span>
                <input type="checkbox" checked={ppeRequired} onChange={(e) => setPpeRequired(e.target.checked)} aria-label="PPE Required" />
              </div>
            )}
            {policy.showSafetyInduction && (
              <div className="rv-toggle-row" id="field-safety">
                <span>Safety Induction Completed *</span>
                <input
                  type="checkbox"
                  checked={safetyInduction}
                  onChange={(e) => setSafetyInduction(e.target.checked)}
                  aria-label="Safety Induction Completed"
                />
              </div>
            )}
            <div className="rv-toggle-row" id="field-policy">
              <span>
                Visitor Policy Accepted *
                <button type="button" className="admin-btn admin-btn--link" onClick={() => setPolicyOpen(true)} style={{ marginLeft: '0.5rem' }}>
                  View policy
                </button>
              </span>
              <input
                type="checkbox"
                checked={policyAccepted}
                onChange={(e) => setPolicyAccepted(e.target.checked)}
                aria-label="Visitor Policy Accepted"
              />
            </div>
          </div>
        </section>

        <section
          id="step-3"
          ref={(el) => { sectionRefs.current[3] = el; }}
          className="rv-section-card"
        >
          <h2 className="rv-section-title">Step 3 — Visit Details</h2>
          {policy.showPoWorkOrder && (
            <div className="rv-grid" style={{ marginBottom: '1rem' }}>
              <div className="reg-form-field">
                <label className="reg-form-label" htmlFor="field-po">PO / Work Order Reference *</label>
                <input
                  id="field-po"
                  className="reg-form-input"
                  value={poReference}
                  onChange={(e) => setPoReference(e.target.value)}
                />
              </div>
              {policy.showWorkPurpose && (
                <div className="reg-form-field">
                  <label className="reg-form-label" htmlFor="field-workPurpose">Work Purpose *</label>
                  <input
                    id="field-workPurpose"
                    className="reg-form-input"
                    value={workPurpose}
                    onChange={(e) => setWorkPurpose(e.target.value)}
                  />
                </div>
              )}
            </div>
          )}
          {!policy.showPoWorkOrder && policy.showWorkPurpose && (
            <div className="rv-grid" style={{ marginBottom: '1rem' }}>
              <div className="reg-form-field">
                <label className="reg-form-label" htmlFor="field-workPurpose">Work Purpose *</label>
                <input
                  id="field-workPurpose"
                  className="reg-form-input"
                  value={workPurpose}
                  onChange={(e) => setWorkPurpose(e.target.value)}
                />
              </div>
            </div>
          )}
          <div className="rv-grid">
            <div className="reg-form-field">
              <label className="reg-form-label" htmlFor="field-purpose">Purpose *</label>
              <select
                id="field-purpose"
                className="reg-form-select"
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
              >
                <option value="">— Select Purpose —</option>
                {PURPOSE_OPTIONS.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>
            <div className="reg-form-field">
              <label className="reg-form-label" htmlFor="field-visitDate">Visit Date *</label>
              <input
                id="field-visitDate"
                type="date"
                className="reg-form-input"
                value={visitDate}
                onChange={(e) => setVisitDate(e.target.value)}
              />
            </div>
            <div className="reg-form-field">
              <label className="reg-form-label" htmlFor="field-arrivalTime">Expected Arrival *</label>
              <input
                id="field-arrivalTime"
                type="time"
                className="reg-form-input"
                value={arrivalTime}
                onChange={(e) => {
                  arrivalTimeTouchedRef.current = true;
                  setArrivalTime(e.target.value);
                }}
              />
            </div>
            <div className="reg-form-field">
              <label className="reg-form-label" htmlFor="field-departureTime">Expected Departure *</label>
              <input
                id="field-departureTime"
                type="time"
                className="reg-form-input"
                value={departureTime}
                onChange={(e) => setDepartureTime(e.target.value)}
              />
            </div>
            <div className="reg-form-field rv-grid--full" id="field-host">
              <label className="reg-form-label">
                Host Employee{policy.hostRequired ? ' *' : ''}
              </label>
              <StaffHostSearch locationId={locationId} value={hostId} onSelect={onHostSelect} disabled={!locationId} />
            </div>
            <div className="reg-form-field">
              <label className="reg-form-label">Host Name</label>
              <input className="reg-form-input" value={hostDisplay?.name ?? ''} readOnly placeholder="Will auto-fill" />
            </div>
            <div className="reg-form-field">
              <label className="reg-form-label">Host Department</label>
              <input className="reg-form-input" value={hostDisplay?.department ?? ''} readOnly placeholder="Will auto-fill" />
            </div>
            <div className="reg-form-field">
              <label className="reg-form-label">Host Email</label>
              <input className="reg-form-input" value={hostDisplay?.email ?? ''} readOnly placeholder="Will auto-fill" />
            </div>
            <div className="reg-form-field">
              <label className="reg-form-label">Host Phone</label>
              <input className="reg-form-input" value="Not available" readOnly />
            </div>
            <div className="reg-form-field">
              <label className="reg-form-label">Vehicle Number</label>
              <input className="reg-form-input" value={vehicleNumber} onChange={(e) => setVehicleNumber(e.target.value)} placeholder="Vehicle number" />
            </div>
            <div className="reg-form-field">
              <label className="reg-form-label">Vehicle Type</label>
              <select className="reg-form-select" value={vehicleType} onChange={(e) => setVehicleType(e.target.value)}>
                {VEHICLE_TYPES.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            <div className="reg-form-field rv-grid--full">
              <label className="reg-form-label">Notes</label>
              <textarea className="reg-form-textarea" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Any additional notes…" rows={3} />
            </div>
            <div className="reg-form-field rv-grid--full">
              <label className="reg-form-label">Assets Carrying</label>
              <div className="rv-assets">
                {ASSET_OPTIONS.map((a) => (
                  <label
                    key={a.key}
                    className={`rv-asset-card ${assets.has(a.key) ? 'rv-asset-card--selected' : ''}`}
                  >
                    <input
                      type="checkbox"
                      checked={assets.has(a.key)}
                      onChange={() => toggleAsset(a.key)}
                      style={{ marginRight: '0.25rem' }}
                    />
                    {a.label}
                  </label>
                ))}
              </div>
              {assets.has('other') && (
                <input
                  className="reg-form-input"
                  style={{ marginTop: '0.75rem' }}
                  value={assetsOther}
                  onChange={(e) => setAssetsOther(e.target.value)}
                  placeholder="Describe item"
                />
              )}
            </div>
          </div>
        </section>

        <section
          id="step-4"
          ref={(el) => { sectionRefs.current[4] = el; }}
          className="rv-section-card"
        >
          <h2 className="rv-section-title">Step 4 — Review & Submit</h2>
          <div className="rv-review-grid">
            {reviewFields.filter((f) => f.show).map((field) => (
              <div key={field.label} className="rv-review-item">
                <label>{field.label}</label>
                <p>{field.value}</p>
              </div>
            ))}
            <div className="rv-review-subsection rv-grid--full">
              <h3 className="rv-review-subtitle">Visit Tracking</h3>
              <div className="rv-review-grid">
                <div className="rv-review-item">
                  <label>Expected Arrival</label>
                  <p>{arrivalTime ? formatTimeLabel(arrivalTime) : '—'}</p>
                </div>
                <div className="rv-review-item">
                  <label>Expected Departure</label>
                  <p>{departureTime ? formatTimeLabel(departureTime) : '—'}</p>
                </div>
                <div className="rv-review-item">
                  <label>Actual Check-In</label>
                  <p className="rv-readonly-value">Not checked in</p>
                </div>
                <div className="rv-review-item">
                  <label>Actual Check-Out</label>
                  <p className="rv-readonly-value">Not checked out</p>
                </div>
              </div>
            </div>
            <div className="rv-review-item rv-review-item--photo">
              <label>Photo</label>
              {photo.previewUrl ? (
                <img src={photo.previewUrl} alt="" className="rv-review-thumb" />
              ) : (
                <p>—</p>
              )}
            </div>
          </div>
          <div className="rv-submit-block">
            {showValidationSummary && validationIssues.length > 0 && (
              <div className="rv-validation-summary" role="alert">
                <p className="rv-validation-summary__title">
                  {validationIssues.length} item{validationIssues.length === 1 ? '' : 's'} still required:
                </p>
                <ul className="rv-validation-summary__list">
                  {validationIssues.map((issue) => (
                    <li key={issue.key}>{issue.message}</li>
                  ))}
                </ul>
              </div>
            )}
            {submitError && <p className="reg-form-error" style={{ marginBottom: '0.75rem' }}>{submitError}</p>}
            <button type="submit" className="admin-btn admin-btn--primary" disabled={submitting}>
              {submitting ? 'Submitting…' : 'Submit Registration'}
            </button>
            {validationIssues.length > 0 && (
              <p className="rv-submit-hint">
                {validationIssues.length} required item{validationIssues.length === 1 ? '' : 's'} remaining before submission.
              </p>
            )}
          </div>
        </section>
      </form>

      <PolicyModal open={policyOpen} onClose={() => setPolicyOpen(false)} />
    </div>
  );
}
