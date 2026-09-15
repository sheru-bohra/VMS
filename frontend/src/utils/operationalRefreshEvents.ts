type Listener = () => void;

const listeners = new Set<Listener>();

/** Notify operational pages to refresh after lifecycle mutations (check-in, approval, etc.). */
export function triggerOperationalRefresh(): void {
  listeners.forEach((fn) => fn());
}

export function subscribeOperationalRefresh(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
