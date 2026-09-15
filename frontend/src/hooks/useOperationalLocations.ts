import { useEffect, useState } from 'react';
import type { AssignedLocation, Location, UserProfile } from '../types';
import { api } from '../services/api';
import { hasPermission } from '../utils/permissions';

export function useOperationalLocations(user: UserProfile | null): Location[] {
  const [locations, setLocations] = useState<Location[]>([]);

  useEffect(() => {
    if (!user) {
      setLocations([]);
      return;
    }
    if (hasPermission(user.permissions, 'locations.read')) {
      api.locations()
        .then(setLocations)
        .catch(() => setLocations([]));
      return;
    }
    const assigned: Location[] = (user.assigned_locations ?? []).map((loc: AssignedLocation) => ({
      id: loc.id,
      name: loc.name,
      code: loc.code,
      city: loc.city,
      is_active: true,
      is_development_seed: false,
    }));
    setLocations(assigned);
  }, [user]);

  return locations;
}
