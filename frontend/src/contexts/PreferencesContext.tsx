import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import type { UserProfile } from '../types';
import {
  DEFAULT_USER_PREFERENCES,
  loadUserPreferences,
  persistResolvedTheme,
  resetUserPreferences,
  resolveThemePreference,
  saveUserPreferences,
  type DensityPreference,
  type ThemePreference,
  type UserPreferences,
} from '../utils/userPreferences';

interface PreferencesContextValue {
  preferences: UserPreferences;
  resolvedTheme: 'light' | 'dark';
  setTheme: (theme: ThemePreference) => void;
  setDensity: (density: DensityPreference) => void;
  setDefaultLocationId: (locationId: number | null) => void;
  setDefaultLandingPage: (path: string | null) => void;
  setReducedMotion: (enabled: boolean) => void;
  resetPreferences: () => void;
}

const PreferencesContext = createContext<PreferencesContextValue | null>(null);

export function PreferencesProvider({ user, children }: { user: UserProfile; children: ReactNode }) {
  const [preferences, setPreferences] = useState<UserPreferences>(() => loadUserPreferences(user.id));

  const persist = useCallback(
    (next: UserPreferences) => {
      setPreferences(next);
      saveUserPreferences(user.id, next);
    },
    [user.id],
  );

  const resolvedTheme = useMemo(
    () => resolveThemePreference(preferences.theme),
    [preferences.theme],
  );

  useEffect(() => {
    persistResolvedTheme(resolvedTheme);
  }, [resolvedTheme]);

  useEffect(() => {
    if (preferences.theme !== 'system' || typeof window.matchMedia !== 'function') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = () => {
      persistResolvedTheme(resolveThemePreference('system'));
    };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [preferences.theme]);

  const setTheme = useCallback(
    (theme: ThemePreference) => persist({ ...preferences, theme }),
    [persist, preferences],
  );

  const setDensity = useCallback(
    (density: DensityPreference) => persist({ ...preferences, density }),
    [persist, preferences],
  );

  const setDefaultLocationId = useCallback(
    (locationId: number | null) => persist({ ...preferences, defaultLocationId: locationId }),
    [persist, preferences],
  );

  const setDefaultLandingPage = useCallback(
    (path: string | null) => persist({ ...preferences, defaultLandingPage: path }),
    [persist, preferences],
  );

  const setReducedMotion = useCallback(
    (enabled: boolean) => persist({ ...preferences, reducedMotion: enabled }),
    [persist, preferences],
  );

  const resetPreferences = useCallback(() => {
    const defaults = resetUserPreferences(user.id);
    setPreferences(defaults);
  }, [user.id]);

  const value = useMemo(
    () => ({
      preferences,
      resolvedTheme,
      setTheme,
      setDensity,
      setDefaultLocationId,
      setDefaultLandingPage,
      setReducedMotion,
      resetPreferences,
    }),
    [
      preferences,
      resolvedTheme,
      setTheme,
      setDensity,
      setDefaultLocationId,
      setDefaultLandingPage,
      setReducedMotion,
      resetPreferences,
    ],
  );

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export function usePreferences(): PreferencesContextValue {
  const ctx = useContext(PreferencesContext);
  if (!ctx) {
    throw new Error('usePreferences must be used within PreferencesProvider');
  }
  return ctx;
}

export function usePreferencesOptional(): PreferencesContextValue | null {
  return useContext(PreferencesContext);
}
