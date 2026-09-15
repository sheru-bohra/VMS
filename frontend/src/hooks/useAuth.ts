import { useCallback, useEffect, useState } from 'react';
import type { UserProfile } from '../types';
import { api, ApiClientError } from '../services/api';
import { isVmsNativeAuthMode } from '../config/auth';
import { getVmsNativeAccessToken } from '../auth/vmsNativeAuth';

interface AuthState {
  user: UserProfile | null;
  loading: boolean;
  error: string | null;
  unauthorized: boolean;
}

export function useAuth() {
  const [state, setState] = useState<AuthState>({
    user: null,
    loading: true,
    error: null,
    unauthorized: false,
  });

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null, unauthorized: false }));
    if (isVmsNativeAuthMode && !getVmsNativeAccessToken()) {
      setState({ user: null, loading: false, error: null, unauthorized: true });
      return;
    }
    try {
      const user = await api.me();
      setState({ user, loading: false, error: null, unauthorized: false });
    } catch (err) {
      if (err instanceof ApiClientError && err.status === 401) {
        setState({ user: null, loading: false, error: null, unauthorized: true });
      } else {
        const message = err instanceof Error ? err.message : 'Failed to load user profile';
        setState({ user: null, loading: false, error: message, unauthorized: false });
      }
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { ...state, reload: load };
}
