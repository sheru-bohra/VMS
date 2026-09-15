import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { HostSearch } from '../../components/visit/HostSearch';
import { PolicyModal } from '../../components/visit/PolicyModal';
import { LoadingState } from '../../components/StatePanels';
import { api, ApiClientError } from '../../services/api';
import type { PublicHost, PublicVisitorType } from '../../types';
import { DURATION_OPTIONS } from '../../types';
import '../../styles/registration.css';

interface FormState {
  visitor_type: string;
  full_name: string;
  mobile: string;
  email: string;
  company: string;
  purpose: string;
  expected_duration_minutes: number;
  policy_accepted: boolean;
}

const INITIAL: FormState = {
  visitor_type: '',
  full_name: '',
  mobile: '',
  email: '',
  company: '',
  purpose: '',
  expected_duration_minutes: 60,
  policy_accepted: false,
};

function validate(form: FormState, host: PublicHost | null): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!form.visitor_type) errors.visitor_type = 'Please select a visitor type.';
  if (!form.full_name.trim() || form.full_name.trim().length < 2) errors.full_name = 'Please enter your full name.';
  if (!form.mobile.trim() || form.mobile.replace(/\D/g, '').length < 7) errors.mobile = 'Please enter a valid mobile number.';
  if (!form.email.trim() || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email)) errors.email = 'Please enter a valid email.';
  if (!form.company.trim()) errors.company = 'Please enter your company.';
  if (!host) errors.host = 'Please select who you are meeting.';
  if (!form.purpose.trim() || form.purpose.trim().length < 2) errors.purpose = 'Please enter a visit purpose.';
  if (!form.policy_accepted) errors.policy = 'You must accept the visitor policy.';
  return errors;
}

export function VisitorRegistrationPage() {
  const { siteToken } = useParams<{ siteToken: string }>();
  const navigate = useNavigate();
  const [siteName, setSiteName] = useState<string | null>(null);
  const [siteError, setSiteError] = useState(false);
  const [loadingSite, setLoadingSite] = useState(true);
  const [visitorTypes, setVisitorTypes] = useState<PublicVisitorType[]>([]);
  const [form, setForm] = useState<FormState>(INITIAL);
  const [host, setHost] = useState<PublicHost | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [policyOpen, setPolicyOpen] = useState(false);
  const firstErrorRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!siteToken) {
      setSiteError(true);
      setLoadingSite(false);
      return;
    }
    setLoadingSite(true);
    api.publicSite(siteToken)
      .then((site) => {
        setSiteName(site.name);
        setSiteError(false);
        return api.publicVisitorTypes(siteToken);
      })
      .then(setVisitorTypes)
      .catch(() => setSiteError(true))
      .finally(() => setLoadingSite(false));
  }, [siteToken]);

  const update = (field: keyof FormState, value: string | number | boolean) => {
    setForm((f) => ({ ...f, [field]: value }));
    setErrors((e) => ({ ...e, [field]: '' }));
    setApiError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!siteToken || submitting) return;

    const fieldErrors = validate(form, host);
    if (Object.keys(fieldErrors).length > 0) {
      setErrors(fieldErrors);
      if (firstErrorRef.current?.scrollIntoView) {
        firstErrorRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      return;
    }

    setSubmitting(true);
    setApiError(null);
    try {
      const result = await api.submitRegistration({
        site_token: siteToken,
        visitor_type: form.visitor_type,
        full_name: form.full_name.trim(),
        mobile: form.mobile.trim(),
        email: form.email.trim(),
        company: form.company.trim(),
        host_id: host!.id,
        purpose: form.purpose.trim(),
        expected_duration_minutes: form.expected_duration_minutes,
        policy_accepted: form.policy_accepted,
      });
      navigate(`/visit/register/${siteToken}/success`, {
        state: {
          reference: result.registration_reference,
          visitorName: result.visitor_name,
          siteName: result.site_name,
          status: result.status,
        },
      });
    } catch (err) {
      const message = err instanceof ApiClientError
        ? err.message
        : "We couldn't submit your registration. Please check your connection and try again. Your entered details have been kept.";
      setApiError(message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loadingSite) {
    return (
      <div className="visitor-page">
        <LoadingState message="Loading registration…" />
      </div>
    );
  }

  if (siteError || !siteName) {
    return (
      <div className="visitor-page">
        <div className="reg-unavailable">
          <h2>Visitor Registration Unavailable</h2>
          <p>This registration link is invalid or no longer active. Please contact reception.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="visitor-page">
      <header className="visitor-header">
        <div className="visitor-logo" aria-hidden="true">VMS</div>
        <h1 className="visitor-title">Visitor Registration</h1>
        <p className="visitor-org">{siteName}</p>
        <p style={{ fontSize: '0.875rem', color: 'var(--color-slate-500)', margin: '0.5rem 0 0' }}>
          Please enter your details to request access.
        </p>
      </header>

      <section className="visitor-card">
        <form className="registration-form" onSubmit={handleSubmit} noValidate>
          <div ref={firstErrorRef} />
          {apiError && <div className="reg-api-error" role="alert">{apiError}</div>}

          <div className="reg-form-field">
            <label className="reg-form-label" htmlFor="visitor_type">Visitor Type</label>
            <select
              id="visitor_type"
              className={`reg-form-select ${errors.visitor_type ? 'reg-form-select--error' : ''}`}
              value={form.visitor_type}
              onChange={(e) => update('visitor_type', e.target.value)}
            >
              <option value="">Select type…</option>
              {visitorTypes.map((t) => (
                <option key={t.code} value={t.code}>{t.name}</option>
              ))}
            </select>
            {errors.visitor_type && <p className="reg-form-error">{errors.visitor_type}</p>}
          </div>

          <div className="reg-form-field">
            <label className="reg-form-label" htmlFor="full_name">Full Name</label>
            <input
              id="full_name"
              type="text"
              className={`reg-form-input ${errors.full_name ? 'reg-form-input--error' : ''}`}
              value={form.full_name}
              onChange={(e) => update('full_name', e.target.value)}
              autoComplete="name"
            />
            {errors.full_name && <p className="reg-form-error">{errors.full_name}</p>}
          </div>

          <div className="reg-form-field">
            <label className="reg-form-label" htmlFor="mobile">Mobile Number</label>
            <input
              id="mobile"
              type="tel"
              inputMode="tel"
              className={`reg-form-input ${errors.mobile ? 'reg-form-input--error' : ''}`}
              value={form.mobile}
              onChange={(e) => update('mobile', e.target.value)}
              autoComplete="tel"
            />
            {errors.mobile && <p className="reg-form-error">{errors.mobile}</p>}
          </div>

          <div className="reg-form-field">
            <label className="reg-form-label" htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              className={`reg-form-input ${errors.email ? 'reg-form-input--error' : ''}`}
              value={form.email}
              onChange={(e) => update('email', e.target.value)}
              autoComplete="email"
            />
            {errors.email && <p className="reg-form-error">{errors.email}</p>}
          </div>

          <div className="reg-form-field">
            <label className="reg-form-label" htmlFor="company">Company</label>
            <input
              id="company"
              type="text"
              className={`reg-form-input ${errors.company ? 'reg-form-input--error' : ''}`}
              value={form.company}
              onChange={(e) => update('company', e.target.value)}
              autoComplete="organization"
            />
            {errors.company && <p className="reg-form-error">{errors.company}</p>}
          </div>

          <div className="reg-form-field">
            <label className="reg-form-label">Who are you meeting?</label>
            {siteToken && (
              <HostSearch siteToken={siteToken} value={host} onChange={setHost} error={errors.host} />
            )}
          </div>

          <div className="reg-form-field">
            <label className="reg-form-label" htmlFor="purpose">Purpose</label>
            <textarea
              id="purpose"
              className={`reg-form-textarea ${errors.purpose ? 'reg-form-textarea--error' : ''}`}
              value={form.purpose}
              onChange={(e) => update('purpose', e.target.value)}
              rows={3}
              maxLength={500}
            />
            {errors.purpose && <p className="reg-form-error">{errors.purpose}</p>}
          </div>

          <div className="reg-form-field">
            <label className="reg-form-label" htmlFor="duration">Expected stay</label>
            <select
              id="duration"
              className="reg-form-select"
              value={form.expected_duration_minutes}
              onChange={(e) => update('expected_duration_minutes', Number(e.target.value))}
            >
              {DURATION_OPTIONS.map((d) => (
                <option key={d.minutes} value={d.minutes}>{d.label}</option>
              ))}
            </select>
          </div>

          <div className="reg-form-field">
            <label className="reg-form-checkbox">
              <input
                type="checkbox"
                checked={form.policy_accepted}
                onChange={(e) => update('policy_accepted', e.target.checked)}
              />
              <span>
                I agree to the{' '}
                <button type="button" onClick={() => setPolicyOpen(true)}>visitor policy</button>
                and premises requirements.
              </span>
            </label>
            {errors.policy && <p className="reg-form-error">{errors.policy}</p>}
          </div>

          <button
            type="submit"
            className="visitor-btn visitor-btn--primary reg-form-submit"
            disabled={submitting}
          >
            {submitting ? 'Submitting…' : 'Submit Registration'}
          </button>
        </form>
      </section>

      <PolicyModal open={policyOpen} onClose={() => setPolicyOpen(false)} />
    </div>
  );
}
