import { useLocation, Navigate } from 'react-router-dom';
import { formatStatus } from '../../types';
import '../../styles/registration.css';

interface SuccessState {
  reference: string;
  visitorName: string;
  siteName: string;
  status: string;
}

export function RegistrationSuccessPage() {
  const location = useLocation();
  const state = location.state as SuccessState | null;

  if (!state?.reference) {
    return <Navigate to="/visit" replace />;
  }

  return (
    <div className="visitor-page">
      <section className="visitor-card reg-success">
        <div className="reg-success__icon" aria-hidden="true">✓</div>
        <h1 className="reg-success__title">Registration received</h1>
        <p style={{ fontSize: '0.9375rem', color: 'var(--color-slate-500)', margin: 0 }}>
          Your request has been sent for approval.
        </p>
        <div className="reg-success__ref">{state.reference}</div>
        <p className="reg-success__detail">Visitor: {state.visitorName}</p>
        <p className="reg-success__detail">Site: {state.siteName}</p>
        <p className="reg-success__detail">Status: {formatStatus(state.status)}</p>
        <p style={{ fontSize: '0.875rem', color: 'var(--color-slate-500)', marginTop: '1.5rem' }}>
          Please remain at reception.
        </p>
      </section>
    </div>
  );
}
