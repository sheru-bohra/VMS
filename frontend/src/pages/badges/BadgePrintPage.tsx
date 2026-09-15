import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../../services/api';
import type { BadgeItem } from '../../types';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import '../../styles/badge-print.css';

export function BadgePrintPage() {
  const { visitId } = useParams<{ visitId: string }>();
  const [badge, setBadge] = useState<BadgeItem | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!visitId) return;
    api.getBadge(Number(visitId))
      .then((b) => {
        setBadge(b);
        return api.printBadge(Number(visitId));
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Badge not available'));
  }, [visitId]);

  if (error) return <ErrorState title="Badge" message={error} />;
  if (!badge) return <LoadingState message="Loading badge…" />;

  const visitDate = badge.visit_date
    ? new Date(badge.visit_date).toLocaleDateString(undefined, { dateStyle: 'medium' })
    : '—';

  return (
    <div className="badge-print-wrap">
      <div className="badge-card" id="badge-print-area">
        <div className="badge-card__brand">Visitor Management System</div>
        <div className="badge-card__title">VISITOR</div>
        <div className="badge-card__name">{badge.visitor_name}</div>
        <div className="badge-card__company">{badge.company ?? '—'}</div>
        <div className="badge-card__row"><span>Type</span><span>{badge.visitor_type ?? '—'}</span></div>
        <div className="badge-card__row"><span>Host</span><span>{badge.host_name ?? '—'}</span></div>
        <div className="badge-card__row"><span>Location</span><span>{badge.site_name}</span></div>
        <div className="badge-card__row"><span>Visit date</span><span>{visitDate}</span></div>
        <div className="badge-card__number">{badge.badge_number}</div>
      </div>
      <button type="button" className="admin-btn admin-btn--primary badge-print-btn" onClick={() => window.print()}>
        Print Badge
      </button>
    </div>
  );
}
