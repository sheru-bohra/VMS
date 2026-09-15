import { useMemo } from 'react';
import type { UserProfile } from '../types';
import { hasPermission } from '../utils/permissions';
import { usePreferencesOptional } from '../contexts/PreferencesContext';
import { isLocationAllowed } from '../utils/userPreferences';

export function usePreferredLocationId(user: UserProfile | null): number | undefined {
  const prefsCtx = usePreferencesOptional();
  const canAccessAll = user ? hasPermission(user.permissions, 'locations.read') : false;

  return useMemo(() => {
    if (!user) return undefined;
    const prefId = prefsCtx?.preferences.defaultLocationId ?? null;
    const allowedIds =
      canAccessAll
        ? user.assigned_locations.map((l) => l.id)
        : user.location_ids;

    if (prefId === null) {
      return canAccessAll ? undefined : allowedIds[0];
    }

    if (isLocationAllowed(prefId, user.location_ids, canAccessAll)) {
      return prefId;
    }

    return canAccessAll ? undefined : allowedIds[0];
  }, [user, prefsCtx?.preferences.defaultLocationId, canAccessAll]);
}
