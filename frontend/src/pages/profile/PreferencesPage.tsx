import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { LoadingState } from '../../components/StatePanels';
import { usePreferences } from '../../contexts/PreferencesContext';
import { useOperationalLocations } from '../../hooks/useOperationalLocations';
import { hasPermission } from '../../utils/permissions';
import {
  getAllowedLandingPages,
  isLocationAllowed,
} from '../../utils/userPreferences';
import '../../styles/admin-pages.css';
import '../../styles/profile-pages.css';

export function PreferencesPage() {
  const { user, loading } = useAuth();
  const location = useLocation();
  const {
    preferences,
    setTheme,
    setDensity,
    setDefaultLocationId,
    setDefaultLandingPage,
    setReducedMotion,
    resetPreferences,
  } = usePreferences();
  const locations = useOperationalLocations(user);
  const canAccessAll = user ? hasPermission(user.permissions, 'locations.read') : false;
  const landingOptions = user ? getAllowedLandingPages(user.permissions) : [];
  const [confirmReset, setConfirmReset] = useState(false);

  useEffect(() => {
    if (location.hash === '#appearance') {
      document.getElementById('appearance-section')?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [location.hash]);

  if (loading || !user) {
    return <LoadingState message="Loading preferences…" />;
  }

  const locationOptions: Array<{ id: number | null; label: string }> = [];
  if (canAccessAll) {
    locationOptions.push({ id: null, label: 'All Locations' });
  }
  for (const loc of locations) {
    locationOptions.push({ id: loc.id, label: loc.name });
  }

  const handleLocationChange = (value: string) => {
    const id = value === '' ? null : Number(value);
    if (isLocationAllowed(id, user.location_ids, canAccessAll)) {
      setDefaultLocationId(id);
    }
  };

  const handleReset = () => {
    if (!confirmReset) {
      setConfirmReset(true);
      return;
    }
    resetPreferences();
    setConfirmReset(false);
  };

  return (
    <div className="preferences-page vms-page-shell">
      <header className="admin-page-header">
        <div>
          <h1 className="admin-page-title">Preferences</h1>
          <p className="admin-page-subtitle">Personal UI settings for your VMS workspace</p>
        </div>
      </header>

      <section id="appearance-section" className="pref-section">
        <h2 className="pref-section__title">Appearance</h2>
        <p className="pref-section__hint">Theme applies to the staff application shell.</p>
        <div className="pref-options">
          {(['system', 'light', 'dark'] as const).map((theme) => (
            <label key={theme} className="pref-radio">
              <input
                type="radio"
                name="theme"
                checked={preferences.theme === theme}
                onChange={() => setTheme(theme)}
              />
              <span>{theme === 'system' ? 'System' : theme === 'light' ? 'Light' : 'Dark'}</span>
            </label>
          ))}
        </div>
      </section>

      <section className="pref-section">
        <h2 className="pref-section__title">Display density</h2>
        <div className="pref-options">
          {(['comfortable', 'compact'] as const).map((density) => (
            <label key={density} className="pref-radio">
              <input
                type="radio"
                name="density"
                checked={preferences.density === density}
                onChange={() => setDensity(density)}
              />
              <span>{density === 'comfortable' ? 'Comfortable' : 'Compact'}</span>
            </label>
          ))}
        </div>
      </section>

      {locationOptions.length > 0 && (
        <section className="pref-section">
          <h2 className="pref-section__title">Default location</h2>
          <p className="pref-section__hint">Preferred location for dashboards and location-scoped views.</p>
          <select
            className="pref-select"
            value={preferences.defaultLocationId ?? ''}
            onChange={(e) => handleLocationChange(e.target.value)}
          >
            {locationOptions.map((opt) => (
              <option key={opt.id ?? 'all'} value={opt.id ?? ''}>
                {opt.label}
              </option>
            ))}
          </select>
        </section>
      )}

      {landingOptions.length > 0 && (
        <section className="pref-section">
          <h2 className="pref-section__title">Default landing page</h2>
          <p className="pref-section__hint">Where to start after signing in.</p>
          <select
            className="pref-select"
            value={preferences.defaultLandingPage ?? ''}
            onChange={(e) => setDefaultLandingPage(e.target.value || null)}
          >
            <option value="">Role default</option>
            {landingOptions.map((opt) => (
              <option key={opt.path} value={opt.path}>{opt.label}</option>
            ))}
          </select>
        </section>
      )}

      <section className="pref-section">
        <h2 className="pref-section__title">Reduced motion</h2>
        <label className="pref-checkbox">
          <input
            type="checkbox"
            checked={preferences.reducedMotion}
            onChange={(e) => setReducedMotion(e.target.checked)}
          />
          <span>Reduce interface motion</span>
        </label>
      </section>

      <section className="pref-section pref-section--footer">
        <button type="button" className="admin-btn admin-btn--secondary" onClick={handleReset}>
          {confirmReset ? 'Confirm reset to defaults' : 'Reset to defaults'}
        </button>
        {confirmReset && (
          <button type="button" className="admin-btn admin-btn--link" onClick={() => setConfirmReset(false)}>
            Cancel
          </button>
        )}
      </section>
    </div>
  );
}
