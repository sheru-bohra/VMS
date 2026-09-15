import { useEffect, useRef } from 'react';
import type { OperationalRefreshKey } from '../utils/operationalRefresh';
import { OPERATIONAL_REFRESH_MS } from '../utils/operationalRefresh';
import { subscribeOperationalRefresh } from '../utils/operationalRefreshEvents';

interface UseOperationalPollingOptions {
  /** When false, polling and focus refresh are disabled. */
  enabled?: boolean;
  /** Immediate load on mount is handled by caller; this hook only polls/refreshes. */
  onRefresh: () => void;
  /** Pause polling when tab is hidden (default true). */
  pauseWhenHidden?: boolean;
  /** Refetch when window gains focus (default true). */
  refetchOnFocus?: boolean;
}

/**
 * Bounded near-real-time refresh for operational pages.
 * Not WebSocket push — polling + focus refresh + shared mutation invalidation.
 */
export function useOperationalPolling(
  key: OperationalRefreshKey,
  options: UseOperationalPollingOptions,
) {
  const {
    enabled = true,
    onRefresh,
    pauseWhenHidden = true,
    refetchOnFocus = true,
  } = options;

  const onRefreshRef = useRef(onRefresh);
  onRefreshRef.current = onRefresh;

  useEffect(() => {
    if (!enabled) return undefined;

    const intervalMs = OPERATIONAL_REFRESH_MS[key];
    let timer: ReturnType<typeof setInterval> | null = null;

    const refresh = () => onRefreshRef.current();

    const startTimer = () => {
      if (timer) clearInterval(timer);
      timer = setInterval(() => {
        if (pauseWhenHidden && document.hidden) return;
        refresh();
      }, intervalMs);
    };

    const onVisibility = () => {
      if (!pauseWhenHidden) return;
      if (!document.hidden) {
        refresh();
        startTimer();
      } else if (timer) {
        clearInterval(timer);
        timer = null;
      }
    };

    const onFocus = () => {
      if (refetchOnFocus && !document.hidden) refresh();
    };

    startTimer();
    if (pauseWhenHidden) document.addEventListener('visibilitychange', onVisibility);
    if (refetchOnFocus) window.addEventListener('focus', onFocus);

    const unsubMutation = subscribeOperationalRefresh(() => {
      if (!document.hidden) refresh();
    });

    return () => {
      if (timer) clearInterval(timer);
      if (pauseWhenHidden) document.removeEventListener('visibilitychange', onVisibility);
      if (refetchOnFocus) window.removeEventListener('focus', onFocus);
      unsubMutation();
    };
  }, [enabled, key, pauseWhenHidden, refetchOnFocus]);
}
