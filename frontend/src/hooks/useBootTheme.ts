import { useEffect, useState } from 'react';
import { readBootResolvedTheme, resolveThemePreference } from '../utils/userPreferences';

/** Resolves staff theme on unauthenticated pages using persisted preference or system setting. */
export function useBootTheme(): 'light' | 'dark' {
  const [theme, setTheme] = useState<'light' | 'dark'>(() =>
    readBootResolvedTheme() ?? resolveThemePreference('system'),
  );

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = () => {
      if (!readBootResolvedTheme()) {
        setTheme(resolveThemePreference('system'));
      }
    };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  return theme;
}
