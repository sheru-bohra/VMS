import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../services/api';
import type { Location, PublicHost, PublicVisitorType } from '../../types';
import { DURATION_OPTIONS } from '../../types';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import { useAuth } from '../../hooks/useAuth';
import { useOperationalLocations } from '../../hooks/useOperationalLocations';
import '../../styles/admin-pages.css';
import '../../styles/registration.css';

export function CreateInvitationPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const locations = useOperationalLocations(user);
  const [visitorTypes, setVisitorTypes] = useState<PublicVisitorType[]>([]);
  const [hosts, setHosts] = useState<PublicHost[]>([]);
  const [locationId, setLocationId] = useState<number | ''>('');
  const [visitorType, setVisitorType] = useState('');
  const [fullName, setFullName] = useState('');
  const [mobile, setMobile] = useState('');
  const [email, setEmail] = useState('');
  const [company, setCompany] = useState('');
  const [hostId, setHostId] = useState<number | ''>('');
  const [visitDate, setVisitDate] = useState('');
  const [arrivalTime, setArrivalTime] = useState('');
  const [duration, setDuration] = useState(60);
  const [purpose, setPurpose] = useState('');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.visitorTypes().then(setVisitorTypes).catch(() => {});
  }, []);

  useEffect(() => {
    if (locations.length === 1) setLocationId(locations[0].id);
  }, [locations]);

  useEffect(() => {
    if (!locationId) {
      setHosts([]);
      return;
    }
    api.locationHosts(Number(locationId)).then(setHosts).catch(() => setHosts([]));
  }, [locationId]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!locationId || !hostId || !visitorType) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.createInvitation({
        location_id: Number(locationId),
        visitor_type: visitorType,
        full_name: fullName,
        mobile,
        email,
        company,
        host_id: Number(hostId),
        visit_date: visitDate,
        arrival_time: arrivalTime,
        expected_duration_minutes: duration,
        purpose,
        notes: notes.trim() || undefined,
      });
      navigate('/invitations');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create visit');
    } finally {
      setSubmitting(false);
    }
  };

  if (!user) return <LoadingState message="Loading…" />;

  return (
    <div className="vms-page-shell">
      <h1 style={{ fontSize: '1.25rem', fontWeight: 600, margin: '0 0 1.5rem' }}>Create Advance Visit</h1>
      {error && <ErrorState title="Unable to create" message={error} />}
      <form onSubmit={submit} className="reg-form" style={{ maxWidth: '640px' }}>
        {locations.length > 1 && (
          <label className="reg-form-label">Location *
            <select className="reg-form-select" value={locationId} onChange={(e) => setLocationId(Number(e.target.value))} required>
              <option value="">Select location…</option>
              {locations.map((l: Location) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          </label>
        )}
        <label className="reg-form-label">Visitor type *
          <select className="reg-form-select" value={visitorType} onChange={(e) => setVisitorType(e.target.value)} required>
            <option value="">Select…</option>
            {visitorTypes.map((t) => <option key={t.code} value={t.code}>{t.name}</option>)}
          </select>
        </label>
        <label className="reg-form-label">Full name *
          <input className="reg-form-input" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
        </label>
        <label className="reg-form-label">Mobile *
          <input className="reg-form-input" value={mobile} onChange={(e) => setMobile(e.target.value)} required />
        </label>
        <label className="reg-form-label">Email *
          <input type="email" className="reg-form-input" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label className="reg-form-label">Company *
          <input className="reg-form-input" value={company} onChange={(e) => setCompany(e.target.value)} required />
        </label>
        <label className="reg-form-label">Host *
          <select className="reg-form-select" value={hostId} onChange={(e) => setHostId(Number(e.target.value))} required>
            <option value="">Select host…</option>
            {hosts.map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
          </select>
        </label>
        <label className="reg-form-label">Visit date *
          <input type="date" className="reg-form-input" value={visitDate} onChange={(e) => setVisitDate(e.target.value)} required />
        </label>
        <label className="reg-form-label">Expected arrival time *
          <input type="time" className="reg-form-input" value={arrivalTime} onChange={(e) => setArrivalTime(e.target.value)} required />
        </label>
        <label className="reg-form-label">Expected duration *
          <select className="reg-form-select" value={duration} onChange={(e) => setDuration(Number(e.target.value))} required>
            {DURATION_OPTIONS.map((d) => <option key={d.minutes} value={d.minutes}>{d.label}</option>)}
          </select>
        </label>
        <label className="reg-form-label">Purpose *
          <textarea className="reg-form-textarea" rows={3} value={purpose} onChange={(e) => setPurpose(e.target.value)} required />
        </label>
        <label className="reg-form-label">Notes
          <textarea className="reg-form-textarea" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </label>
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
          <button type="button" className="admin-btn" onClick={() => navigate('/invitations')}>Cancel</button>
          <button type="submit" className="admin-btn admin-btn--primary" disabled={submitting}>
            {submitting ? 'Creating…' : 'Create Visit'}
          </button>
        </div>
      </form>
    </div>
  );
}
