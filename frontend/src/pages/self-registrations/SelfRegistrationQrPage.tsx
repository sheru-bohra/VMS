import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import QRCode from 'qrcode';
import { api } from '../../services/api';
import type { SelfRegistrationQrConfig } from '../../types';
import { useAuth } from '../../hooks/useAuth';
import { useOperationalLocations } from '../../hooks/useOperationalLocations';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import { SelfRegistrationSubnav } from './SelfRegistrationSubnav';
import { buildQrPdfFilename, qrDataUrl } from './qrRegistrationUtils';
import '../../styles/admin-pages.css';
import '../../styles/self-registration-qr.css';

const POLL_INTERVAL = 30000;

function PhoneQrIcon() {
  return (
    <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <rect x="7" y="2" width="10" height="20" rx="2" />
      <path d="M11 18h2" />
    </svg>
  );
}

function ReceptionQrPoster({
  config,
  qrCanvasRef,
  fullscreen = false,
}: {
  config: SelfRegistrationQrConfig;
  qrCanvasRef: React.RefObject<HTMLCanvasElement | null>;
  fullscreen?: boolean;
}) {
  return (
    <div className={`sr-qr-poster ${fullscreen ? 'sr-qr-poster--fullscreen' : ''}`} data-reception-qr-print>
      <div className="sr-qr-poster__brand">
        <img src="/payu-logo.jpg" alt="PayU" className="sr-qr-poster__logo" />
      </div>
      <h2 className="sr-qr-poster__title">Visitor Self Registration</h2>
      <p className="sr-qr-poster__subtitle">Scan the QR code to register your visit</p>
      <div className="sr-qr-poster__frame">
        <canvas ref={qrCanvasRef} className="sr-qr-poster__canvas" aria-label="Self-registration QR code" />
      </div>
      <p className="sr-qr-poster__location">{config.location.name}</p>
      <p className="sr-qr-poster__company">{config.company_label}</p>
      <p className="sr-qr-poster__status">Permanent Reception QR</p>
      <div className="sr-qr-poster__accent" aria-hidden="true" />
    </div>
  );
}

export function SelfRegistrationQrPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const fallbackLocations = useOperationalLocations(user);
  const [locationId, setLocationId] = useState<number | undefined>();
  const [config, setConfig] = useState<SelfRegistrationQrConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copyHint, setCopyHint] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const qrCanvasRef = useRef<HTMLCanvasElement>(null);
  const posterHostRef = useRef<HTMLDivElement>(null);
  const registrationUrlRef = useRef<string>('');

  const load = useCallback(async (site?: number) => {
    setError(null);
    try {
      const data = await api.selfRegistrationQrConfig(site);
      setConfig(data);
      if (!site) {
        setLocationId(data.location.id);
      }
    } catch (err) {
      setConfig(null);
      setError(err instanceof Error ? err.message : 'Failed to load reception QR');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    load(locationId);
  }, [locationId, load]);

  useEffect(() => {
    const onVisibility = () => {
      if (!document.hidden && locationId) load(locationId);
    };
    const timer = setInterval(() => {
      if (!document.hidden && locationId) load(locationId);
    }, POLL_INTERVAL);
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [load, locationId]);

  useEffect(() => {
    const url = config?.registration_url ?? '';
    registrationUrlRef.current = url;
    if (!url || !qrCanvasRef.current) return;
    const size = isFullscreen ? 420 : 340;
    QRCode.toCanvas(qrCanvasRef.current, url, {
      width: size,
      margin: 2,
      errorCorrectionLevel: 'M',
      color: { dark: '#000000', light: '#ffffff' },
    }).catch(() => undefined);
  }, [config?.registration_url, isFullscreen]);

  useEffect(() => {
    const onFsChange = () => setIsFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener('fullscreenchange', onFsChange);
    return () => document.removeEventListener('fullscreenchange', onFsChange);
  }, []);

  const locationOptions = config?.locations.length
    ? config.locations
    : fallbackLocations;

  const showLocationSelect = locationOptions.length > 1;

  const handleCopyUrl = async () => {
    if (!config?.registration_url) return;
    try {
      await navigator.clipboard.writeText(config.registration_url);
      setCopyHint('Copied');
      setTimeout(() => setCopyHint(null), 2000);
    } catch {
      setCopyHint('Unable to copy');
    }
  };

  const handleRefresh = () => {
    setLoading(true);
    load(locationId);
  };

  const handleFullscreen = async () => {
    const el = posterHostRef.current;
    if (!el) return;
    if (document.fullscreenElement) {
      await document.exitFullscreen();
      return;
    }
    try {
      await el.requestFullscreen();
    } catch {
      /* ignore */
    }
  };

  const handlePrint = () => {
    window.print();
  };

  const handleDownloadPdf = async () => {
    if (!config) return;
    const dataUrl = await qrDataUrl(config.registration_url, 512);
    const { jsPDF } = await import('jspdf');
    const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
    const pageWidth = doc.internal.pageSize.getWidth();
    let y = 24;
    doc.setFontSize(18);
    doc.text('Visitor Self Registration', pageWidth / 2, y, { align: 'center' });
    y += 8;
    doc.setFontSize(11);
    doc.text('Scan the QR code to register your visit', pageWidth / 2, y, { align: 'center' });
    y += 12;
    const qrSize = 90;
    doc.addImage(dataUrl, 'PNG', (pageWidth - qrSize) / 2, y, qrSize, qrSize);
    y += qrSize + 10;
    doc.setFontSize(14);
    doc.text(config.location.name, pageWidth / 2, y, { align: 'center' });
    y += 7;
    doc.setFontSize(12);
    doc.text(config.company_label, pageWidth / 2, y, { align: 'center' });
    y += 10;
    doc.setFontSize(9);
    const urlLines = doc.splitTextToSize(config.registration_url, pageWidth - 40);
    doc.text(urlLines, pageWidth / 2, y, { align: 'center' });
    doc.save(buildQrPdfFilename(config.company_label, config.location.name));
  };

  const viewPending = () => {
    const params = new URLSearchParams();
    params.set('tab', 'PENDING_APPROVAL');
    if (config?.location.id) params.set('site', String(config.location.id));
    navigate(`/self-registrations?${params.toString()}`);
  };

  if (loading && !config) return <LoadingState message="Loading reception QR…" />;
  if (error && !config) {
    return (
      <div>
        <SelfRegistrationSubnav />
        <ErrorState title="Unable to load reception QR" message={error} action={{ label: 'Retry', onClick: () => { setLoading(true); load(locationId); } }} />
      </div>
    );
  }

  if (!config) return null;

  return (
    <div className="sr-qr-page vms-page-shell">
      <SelfRegistrationSubnav />

      <header className="sr-qr-header">
        <div className="sr-qr-header__title-row">
          <PhoneQrIcon />
          <div>
            <h1 className="sr-qr-header__title">Visitor Self Registration QR</h1>
            <p className="sr-qr-header__subtitle">
              Display this QR code at your reception desk so visitors can self-register without staff assistance.
            </p>
          </div>
        </div>
        {showLocationSelect && (
          <label className="sr-qr-location-select">
            <span>Location</span>
            <select
              value={locationId ?? config.location.id}
              onChange={(e) => setLocationId(Number(e.target.value))}
            >
              {locationOptions.map((loc) => (
                <option key={loc.id} value={loc.id}>{loc.name}</option>
              ))}
            </select>
          </label>
        )}
        {!showLocationSelect && (
          <p className="sr-qr-location-readonly">
            <span>Location</span> {config.location.name}
          </p>
        )}
      </header>

      {config.localhost_warning && (
        <p className="sr-qr-dev-warning" role="status">
          Mobile devices cannot access localhost. Configure a reachable LAN or staging public URL before printing this QR.
        </p>
      )}

      <div className="sr-qr-layout">
        <div className="sr-qr-layout__left" ref={posterHostRef}>
          <ReceptionQrPoster config={config} qrCanvasRef={qrCanvasRef} fullscreen={isFullscreen} />
        </div>

        <div className="sr-qr-layout__right">
          <section className="sr-qr-info-card">
            <h2 className="sr-qr-info-card__title">Location Info</h2>
            <dl className="sr-qr-info-list">
              <div>
                <dt>Location</dt>
                <dd>{config.location.name}</dd>
              </div>
              <div>
                <dt>Company</dt>
                <dd>{config.company_label}</dd>
              </div>
              <div>
                <dt>Registration URL</dt>
                <dd className="sr-qr-url-row">
                  <span className="sr-qr-url-text">{config.registration_url}</span>
                  <button type="button" className="admin-btn admin-btn--sm" onClick={handleCopyUrl}>
                    Copy URL
                  </button>
                  {copyHint && <span className="sr-qr-copy-hint">{copyHint}</span>}
                </dd>
              </div>
            </dl>
          </section>

          <section className="sr-qr-info-card">
            <h2 className="sr-qr-info-card__title">How It Works</h2>
            <ol className="sr-qr-steps">
              <li>Visitor scans the reception QR code using their phone camera.</li>
              <li>Visitor enters personal and visit details and accepts required policies.</li>
              <li>Host, reception, or security reviews the registration where approval is required.</li>
              <li>Once approved, the visitor proceeds through the existing check-in and badge workflow.</li>
            </ol>
          </section>

          <section className="sr-qr-info-card">
            <h2 className="sr-qr-info-card__title">Today&apos;s Stats</h2>
            <div className="sr-qr-stats-grid">
              <div className="sr-qr-stat">
                <span className="sr-qr-stat__label">Today</span>
                <span className="sr-qr-stat__value">{config.stats.today}</span>
              </div>
              <div className="sr-qr-stat">
                <span className="sr-qr-stat__label">Pending</span>
                <span className="sr-qr-stat__value">{config.stats.pending}</span>
              </div>
              <div className="sr-qr-stat">
                <span className="sr-qr-stat__label">Approved</span>
                <span className="sr-qr-stat__value">{config.stats.approved}</span>
              </div>
              <div className="sr-qr-stat">
                <span className="sr-qr-stat__label">Rejected</span>
                <span className="sr-qr-stat__value">{config.stats.rejected}</span>
              </div>
            </div>
          </section>
        </div>
      </div>

      <div className="sr-qr-toolbar no-print">
        <button type="button" className="admin-btn admin-btn--primary" onClick={handleRefresh}>
          Refresh QR
        </button>
        <button type="button" className="admin-btn admin-btn--outline" onClick={handleFullscreen}>
          Fullscreen
        </button>
        <button type="button" className="admin-btn admin-btn--outline" onClick={handlePrint}>
          Print
        </button>
        <button type="button" className="admin-btn admin-btn--outline" onClick={handleDownloadPdf}>
          Download A4 PDF
        </button>
        <button type="button" className="admin-btn admin-btn--outline" onClick={viewPending}>
          View Pending ({config.stats.pending})
        </button>
      </div>
    </div>
  );
}
