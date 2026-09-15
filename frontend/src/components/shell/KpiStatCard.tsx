import { Link } from 'react-router-dom';
import { NavIcon } from '../admin/NavIcon';
import type { NavIconName, NavIconTone } from '../../utils/navigationConfig';

export type KpiAccent = 'cyan' | 'amber' | 'green' | 'violet' | 'orange' | 'blue';

interface KpiStatCardProps {
  label: string;
  value: number;
  icon: NavIconName;
  tone: NavIconTone;
  accent?: KpiAccent;
  hint?: string;
  variant?: 'default' | 'compact';
  to?: string;
  onClick?: () => void;
  ariaLabel?: string;
}

export function KpiStatCard({
  label,
  value,
  icon,
  tone,
  accent,
  hint,
  variant = 'default',
  to,
  onClick,
  ariaLabel,
}: KpiStatCardProps) {
  const accentClass = accent ? `kpi-stat-card--accent-${accent}` : '';
  const variantClass = variant === 'compact' ? 'kpi-stat-card--compact' : '';
  const interactiveClass = to || onClick ? 'kpi-stat-card--interactive' : '';
  const className = `kpi-stat-card ${accentClass} ${variantClass} ${interactiveClass}`.trim();
  const content = (
    <>
      <NavIcon name={icon} tone={tone} className="kpi-stat-card__icon" />
      <div className="kpi-stat-card__value">{value}</div>
      <div className="kpi-stat-card__label">{label}</div>
      {hint ? <div className="kpi-stat-card__hint">{hint}</div> : null}
    </>
  );

  if (to) {
    return (
      <Link
        to={to}
        className={className}
        aria-label={ariaLabel ?? `${label}: ${value}`}
      >
        {content}
      </Link>
    );
  }

  if (onClick) {
    return (
      <button
        type="button"
        className={className}
        onClick={onClick}
        aria-label={ariaLabel ?? `${label}: ${value}`}
      >
        {content}
      </button>
    );
  }

  return <div className={className}>{content}</div>;
}
