import { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import QRCode from 'qrcode';
import { api } from '../../services/api';
import type { PublicInvitation } from '../../types';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import '../../styles/registration.css';

export function VisitorInvitationPage() {
  const { token } = useParams<{ token: string }>();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [data, setData] = useState<PublicInvitation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    api.publicInvitation(token)
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : 'Invitation not available'))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    if (!data || !canvasRef.current || !token) return;
    const url = `${window.location.origin}/visit/invitation/${token}`;
    QRCode.toCanvas(canvasRef.current, url, { width: Math.min(280, window.innerWidth - 48), margin: 2 });
  }, [data, token]);

  if (loading) return <LoadingState message="Loading invitation…" />;
  if (error || !data) return <ErrorState title="Invitation unavailable" message={error ?? 'Not found'} />;

  const schedule = data.scheduled_start
    ? new Date(data.scheduled_start).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
    : '—';

  return (
    <div className="reg-page" style={{ padding: '1.25rem', maxWidth: '420px', margin: '0 auto', paddingBottom: 'env(safe-area-inset-bottom)' }}>
      <p style={{ fontSize: '0.8125rem', color: 'var(--color-slate-500)', margin: '0 0 0.5rem' }}>Visitor Invitation</p>
      <p style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--color-success)', margin: '0 0 1rem' }}>✓ Visit Approved</p>
      <h1 style={{ fontSize: '1.375rem', fontWeight: 700, margin: '0 0 0.25rem', lineHeight: 1.3 }}>{data.visitor_name}</h1>
      {data.company && <p style={{ margin: '0 0 1rem', color: 'var(--color-slate-600)' }}>{data.company}</p>}
      <p style={{ margin: '0 0 0.25rem', fontWeight: 500 }}>{data.site_name}</p>
      <p style={{ margin: '0 0 1rem', color: 'var(--color-slate-600)' }}>{schedule}</p>
      <div style={{ marginBottom: '1rem' }}>
        <div style={{ fontSize: '0.75rem', color: 'var(--color-slate-500)' }}>Host</div>
        <div>{data.host_name ?? '—'}</div>
      </div>
      <div style={{ marginBottom: '1.5rem' }}>
        <div style={{ fontSize: '0.75rem', color: 'var(--color-slate-500)' }}>Purpose</div>
        <div>{data.purpose ?? '—'}</div>
      </div>
      <p style={{ textAlign: 'center', fontSize: '0.875rem', margin: '0 0 1rem' }}>Please present this QR at reception.</p>
      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1rem' }}>
        <canvas ref={canvasRef} aria-label="Visitor invitation QR code" />
      </div>
    </div>
  );
}
