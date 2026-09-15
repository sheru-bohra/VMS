import type { DashboardTrendPoint } from '../../types';

interface SeriesConfig {
  key: 'checked_in' | 'checked_out' | 'expected';
  label: string;
  colorVar: string;
}

const SERIES: SeriesConfig[] = [
  { key: 'expected', label: 'Expected', colorVar: '--vms-chart-secondary' },
  { key: 'checked_in', label: 'Check-ins', colorVar: '--vms-primary' },
  { key: 'checked_out', label: 'Check-outs', colorVar: '--vms-chart-primary' },
];

function trendLabel(point: DashboardTrendPoint): string {
  if (point.label) return point.label;
  if (point.date.length >= 10) return point.date.slice(5, 10);
  return point.date;
}

function hasActivity(points: DashboardTrendPoint[]): boolean {
  return points.some(
    (p) => p.expected > 0 || p.checked_in > 0 || p.checked_out > 0,
  );
}

function buildPath(
  values: number[],
  maxVal: number,
  width: number,
  height: number,
  padding: { top: number; bottom: number; left: number; right: number },
): string {
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;
  const n = values.length;
  if (n === 0) return '';

  const step = n > 1 ? plotW / (n - 1) : 0;
  const points = values.map((v, i) => {
    const x = padding.left + (n > 1 ? i * step : plotW / 2);
    const y = padding.top + plotH - (maxVal > 0 ? (v / maxVal) * plotH : 0);
    return `${x},${y}`;
  });
  return `M ${points.join(' L ')}`;
}

export function VisitorActivityChart({ points }: { points: DashboardTrendPoint[] }) {
  if (!hasActivity(points)) {
    return (
      <p className="section-card__empty visitor-activity-chart__empty">
        No visitor activity for the selected period.
      </p>
    );
  }

  const width = 640;
  const height = 200;
  const padding = { top: 12, right: 12, bottom: 28, left: 36 };
  const labels = points.map(trendLabel);
  const maxVal = Math.max(
    1,
    ...points.flatMap((p) => [p.expected, p.checked_in, p.checked_out]),
  );
  const yTicks = [0, Math.ceil(maxVal / 2), maxVal];

  return (
    <div className="visitor-activity-chart" role="img" aria-label="Visitor activity chart">
      <svg
        className="visitor-activity-chart__svg"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="xMidYMid meet"
      >
        {yTicks.map((tick) => {
          const y =
            padding.top +
            (height - padding.top - padding.bottom) -
            (maxVal > 0 ? (tick / maxVal) * (height - padding.top - padding.bottom) : 0);
          return (
            <g key={tick} className="visitor-activity-chart__grid">
              <line
                x1={padding.left}
                y1={y}
                x2={width - padding.right}
                y2={y}
              />
              <text x={padding.left - 6} y={y + 4} textAnchor="end" className="visitor-activity-chart__axis">
                {tick}
              </text>
            </g>
          );
        })}

        {SERIES.map((series) => (
          <path
            key={series.key}
            d={buildPath(
              points.map((p) => p[series.key]),
              maxVal,
              width,
              height,
              padding,
            )}
            fill="none"
            className="visitor-activity-chart__line"
            style={{ stroke: `var(${series.colorVar}, #64748b)` }}
            strokeWidth={2}
          />
        ))}

        {labels.map((label, i) => {
          const n = labels.length;
          const plotW = width - padding.left - padding.right;
          const x = padding.left + (n > 1 ? (i * plotW) / (n - 1) : plotW / 2);
          return (
            <text
              key={`${label}-${i}`}
              x={x}
              y={height - 6}
              textAnchor="middle"
              className="visitor-activity-chart__axis visitor-activity-chart__axis--x"
            >
              {label}
            </text>
          );
        })}
      </svg>

      <ul className="visitor-activity-chart__legend" aria-hidden="true">
        {SERIES.map((s) => (
          <li key={s.key}>
            <span
              className="visitor-activity-chart__legend-swatch"
              style={{ background: `var(${s.colorVar}, #64748b)` }}
            />
            {s.label}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function visitorTrendHasActivity(points: DashboardTrendPoint[] | undefined): boolean {
  return hasActivity(points ?? []);
}
