import { useEffect, useState } from 'react';
import { OPERATIONAL_REFRESH_MS } from '../../utils/operationalRefresh';

interface RefreshStatusProps {
  lastUpdated: Date | null;
  refreshing: boolean;
  intervalKey?: keyof typeof OPERATIONAL_REFRESH_MS;
}

export function RefreshStatus({
  lastUpdated,
  refreshing,
  intervalKey = 'dashboard',
}: RefreshStatusProps) {
  const intervalMs = OPERATIONAL_REFRESH_MS[intervalKey];
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const tick = () => {
      if (!lastUpdated || refreshing) {
        setSeconds(0);
        return;
      }
      const elapsed = Date.now() - lastUpdated.getTime();
      const remaining = Math.max(0, Math.ceil((intervalMs - elapsed) / 1000));
      setSeconds(remaining);
    };
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [lastUpdated, refreshing, intervalMs]);

  if (!lastUpdated) return null;

  const label = refreshing
    ? 'Updating…'
    : seconds > 0
      ? `Live · refresh in ${seconds}s`
      : 'Updated just now';

  return (
    <div className="vms-refresh-status" aria-live="polite">
      <span className="vms-refresh-status__dot" aria-hidden="true" />
      {label}
    </div>
  );
}
