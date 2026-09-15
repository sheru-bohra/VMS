import { useCallback, useEffect, useState } from 'react';
import { api } from '../../services/api';
import type { Location } from '../../types';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import '../../styles/admin-pages.css';

type Tab = 'profiles' | 'mappings' | 'printers' | 'locations';

interface ProfileRow {
  id: number;
  location_id: number;
  name: string;
  description: string | null;
  provider_external_profile_ref: string;
  is_active: boolean;
}

interface MappingRow {
  id: number;
  location_id: number;
  visitor_type_id: number;
  visitor_type_name: string | null;
  access_profile_id: number;
  access_profile_name: string | null;
  is_active: boolean;
}

interface PrinterRow {
  id: number;
  location_id: number;
  name: string;
  provider_key: string;
  provider_external_printer_ref: string;
  is_default: boolean;
  is_active: boolean;
}

interface LocationConfigRow {
  id: number;
  location_id: number;
  location_name: string | null;
  access_control_enabled: boolean;
  provider_key: string;
  default_access_profile_id: number | null;
  credential_grace_minutes: number;
  max_credential_duration_minutes: number;
}

interface VisitorTypeRow {
  id: number;
  name: string;
  code: string;
}

export function AccessBadgesAdminPage() {
  const [tab, setTab] = useState<Tab>('profiles');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [canManageAccess, setCanManageAccess] = useState(false);
  const [canManagePrinter, setCanManagePrinter] = useState(false);
  const [locations, setLocations] = useState<Location[]>([]);
  const [visitorTypes, setVisitorTypes] = useState<VisitorTypeRow[]>([]);
  const [profiles, setProfiles] = useState<ProfileRow[]>([]);
  const [mappings, setMappings] = useState<MappingRow[]>([]);
  const [printers, setPrinters] = useState<PrinterRow[]>([]);
  const [locationConfigs, setLocationConfigs] = useState<LocationConfigRow[]>([]);

  const [profileFormOpen, setProfileFormOpen] = useState(false);
  const [editingProfile, setEditingProfile] = useState<ProfileRow | null>(null);
  const [profileLocationId, setProfileLocationId] = useState<number>(0);
  const [profileName, setProfileName] = useState('');
  const [profileDescription, setProfileDescription] = useState('');
  const [profileRef, setProfileRef] = useState('');
  const [profileFormError, setProfileFormError] = useState<string | null>(null);
  const [profileSaving, setProfileSaving] = useState(false);
  const [deactivateProfileId, setDeactivateProfileId] = useState<number | null>(null);

  const [mappingFormOpen, setMappingFormOpen] = useState(false);
  const [editingMapping, setEditingMapping] = useState<MappingRow | null>(null);
  const [mappingLocationId, setMappingLocationId] = useState<number>(0);
  const [mappingVisitorTypeId, setMappingVisitorTypeId] = useState<number>(0);
  const [mappingProfileId, setMappingProfileId] = useState<number>(0);
  const [mappingFormError, setMappingFormError] = useState<string | null>(null);
  const [mappingSaving, setMappingSaving] = useState(false);

  const [printerFormOpen, setPrinterFormOpen] = useState(false);
  const [editingPrinter, setEditingPrinter] = useState<PrinterRow | null>(null);
  const [printerLocationId, setPrinterLocationId] = useState<number>(0);
  const [printerName, setPrinterName] = useState('');
  const [printerProvider, setPrinterProvider] = useState('dev_mock');
  const [printerRef, setPrinterRef] = useState('');
  const [printerDefault, setPrinterDefault] = useState(false);
  const [printerFormError, setPrinterFormError] = useState<string | null>(null);
  const [printerSaving, setPrinterSaving] = useState(false);
  const [deactivatePrinterId, setDeactivatePrinterId] = useState<number | null>(null);

  const [editingLocationId, setEditingLocationId] = useState<number | null>(null);
  const [enableConfirmLocationId, setEnableConfirmLocationId] = useState<number | null>(null);
  const [locEnabled, setLocEnabled] = useState(false);
  const [locGrace, setLocGrace] = useState(30);
  const [locMax, setLocMax] = useState(480);
  const [locDefaultProfileId, setLocDefaultProfileId] = useState<number | ''>('');
  const [locFormError, setLocFormError] = useState<string | null>(null);
  const [locSaving, setLocSaving] = useState(false);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const me = await api.me();
      setCanManageAccess(me.permissions.includes('access.config.manage'));
      setCanManagePrinter(me.permissions.includes('badge.printer.config.manage'));
      const [locs, vtypes, p, m, pr, lc] = await Promise.all([
        api.locations(),
        api.visitorTypes(),
        api.accessProfiles(),
        api.accessProfileMappings(),
        api.badgePrinters(),
        api.accessLocationConfigs(),
      ]);
      setLocations(locs);
      setVisitorTypes(vtypes as VisitorTypeRow[]);
      setProfiles(p as ProfileRow[]);
      setMappings(m as MappingRow[]);
      setPrinters(pr as PrinterRow[]);
      setLocationConfigs(lc as LocationConfigRow[]);
      if (locs.length > 0 && profileLocationId === 0) {
        setProfileLocationId(locs[0].id);
        setMappingLocationId(locs[0].id);
        setPrinterLocationId(locs[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [profileLocationId]);

  useEffect(() => {
    load();
  }, [load]);

  const profilesForLocation = (locationId: number) =>
    profiles.filter((p) => p.location_id === locationId && p.is_active);

  const openCreateProfile = () => {
    setEditingProfile(null);
    setProfileName('');
    setProfileDescription('');
    setProfileRef('');
    setProfileFormError(null);
    setProfileFormOpen(true);
  };

  const openEditProfile = (p: ProfileRow) => {
    setEditingProfile(p);
    setProfileLocationId(p.location_id);
    setProfileName(p.name);
    setProfileDescription(p.description ?? '');
    setProfileRef(p.provider_external_profile_ref);
    setProfileFormError(null);
    setProfileFormOpen(true);
  };

  const saveProfile = async () => {
    setProfileSaving(true);
    setProfileFormError(null);
    try {
      if (editingProfile) {
        await api.updateAccessProfile(editingProfile.id, {
          name: profileName,
          description: profileDescription || null,
          provider_external_profile_ref: profileRef,
        });
        showToast('Access profile updated');
      } else {
        await api.createAccessProfile({
          location_id: profileLocationId,
          name: profileName,
          description: profileDescription || null,
          provider_external_profile_ref: profileRef,
        });
        showToast('Access profile created');
      }
      setProfileFormOpen(false);
      await load();
    } catch (err) {
      setProfileFormError(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setProfileSaving(false);
    }
  };

  const confirmDeactivateProfile = async () => {
    if (!deactivateProfileId) return;
    try {
      await api.deactivateAccessProfile(deactivateProfileId);
      setDeactivateProfileId(null);
      showToast('Profile deactivated');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Deactivate failed');
    }
  };

  const openCreateMapping = () => {
    setEditingMapping(null);
    setMappingFormError(null);
    setMappingFormOpen(true);
  };

  const openEditMapping = (m: MappingRow) => {
    setEditingMapping(m);
    setMappingLocationId(m.location_id);
    setMappingVisitorTypeId(m.visitor_type_id);
    setMappingProfileId(m.access_profile_id);
    setMappingFormError(null);
    setMappingFormOpen(true);
  };

  const saveMapping = async () => {
    setMappingSaving(true);
    setMappingFormError(null);
    try {
      if (editingMapping) {
        await api.updateAccessProfileMapping(editingMapping.id, { access_profile_id: mappingProfileId });
        showToast('Mapping updated');
      } else {
        await api.createAccessProfileMapping({
          location_id: mappingLocationId,
          visitor_type_id: mappingVisitorTypeId,
          access_profile_id: mappingProfileId,
        });
        showToast('Mapping created');
      }
      setMappingFormOpen(false);
      await load();
    } catch (err) {
      setMappingFormError(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setMappingSaving(false);
    }
  };

  const deactivateMapping = async (id: number) => {
    try {
      await api.deactivateAccessProfileMapping(id);
      showToast('Mapping deactivated');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Deactivate failed');
    }
  };

  const openCreatePrinter = () => {
    setEditingPrinter(null);
    setPrinterName('');
    setPrinterProvider('dev_mock');
    setPrinterRef('');
    setPrinterDefault(false);
    setPrinterFormError(null);
    setPrinterFormOpen(true);
  };

  const openEditPrinter = (p: PrinterRow) => {
    setEditingPrinter(p);
    setPrinterLocationId(p.location_id);
    setPrinterName(p.name);
    setPrinterProvider(p.provider_key);
    setPrinterRef(p.provider_external_printer_ref);
    setPrinterDefault(p.is_default);
    setPrinterFormError(null);
    setPrinterFormOpen(true);
  };

  const savePrinter = async () => {
    setPrinterSaving(true);
    setPrinterFormError(null);
    try {
      if (editingPrinter) {
        await api.updateBadgePrinter(editingPrinter.id, {
          name: printerName,
          provider_external_printer_ref: printerRef,
          is_default: printerDefault,
        });
        showToast('Printer updated');
      } else {
        await api.createBadgePrinter({
          location_id: printerLocationId,
          name: printerName,
          provider_key: printerProvider,
          provider_external_printer_ref: printerRef,
          is_default: printerDefault,
        });
        showToast('Printer created');
      }
      setPrinterFormOpen(false);
      await load();
    } catch (err) {
      setPrinterFormError(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setPrinterSaving(false);
    }
  };

  const confirmDeactivatePrinter = async () => {
    if (!deactivatePrinterId) return;
    try {
      await api.deactivateBadgePrinter(deactivatePrinterId);
      setDeactivatePrinterId(null);
      showToast('Printer deactivated');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Deactivate failed');
    }
  };

  const openEditLocation = (cfg: LocationConfigRow) => {
    setEditingLocationId(cfg.location_id);
    setLocEnabled(cfg.access_control_enabled);
    setLocGrace(cfg.credential_grace_minutes);
    setLocMax(cfg.max_credential_duration_minutes);
    setLocDefaultProfileId(cfg.default_access_profile_id ?? '');
    setLocFormError(null);
  };

  const saveLocationConfig = async (enableOverride?: boolean) => {
    if (!editingLocationId) return;
    const enabling = enableOverride ?? locEnabled;
    if (enabling && !locEnabled && enableConfirmLocationId !== editingLocationId) {
      setEnableConfirmLocationId(editingLocationId);
      return;
    }
    setLocSaving(true);
    setLocFormError(null);
    try {
      await api.updateAccessLocationConfig(editingLocationId, {
        access_control_enabled: enabling,
        credential_grace_minutes: locGrace,
        max_credential_duration_minutes: locMax,
        default_access_profile_id: locDefaultProfileId === '' ? null : locDefaultProfileId,
      });
      setEnableConfirmLocationId(null);
      setEditingLocationId(null);
      showToast('Location configuration saved');
      await load();
    } catch (err) {
      setLocFormError(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setLocSaving(false);
    }
  };

  if (loading) return <LoadingState message="Loading access & badge configuration…" />;
  if (error) return <ErrorState title="Unable to load" message={error} action={{ label: 'Retry', onClick: load }} />;

  const locName = locations.find((l) => l.id === enableConfirmLocationId)?.name ?? 'this location';

  return (
    <div className="vms-page-shell">
      {toast && (
        <div className="admin-card" style={{ marginBottom: '0.75rem', background: 'var(--color-slate-100)' }}>
          {toast}
        </div>
      )}

      <div className="admin-page-header">
        <div>
          <h1 className="admin-page-title">Access & Badge Administration</h1>
          <p className="admin-page-subtitle">Access profiles, visitor mappings, and printer configuration.</p>
        </div>
        {tab === 'profiles' && canManageAccess && (
          <button type="button" className="admin-btn admin-btn--primary" onClick={openCreateProfile}>
            Create profile
          </button>
        )}
        {tab === 'mappings' && canManageAccess && (
          <button type="button" className="admin-btn admin-btn--primary" onClick={openCreateMapping}>
            Create mapping
          </button>
        )}
        {tab === 'printers' && canManagePrinter && (
          <button type="button" className="admin-btn admin-btn--primary" onClick={openCreatePrinter}>
            Add printer
          </button>
        )}
      </div>

      <div className="access-badges-tab-bar" role="tablist" aria-label="Access and badge sections">
        {(['profiles', 'mappings', 'printers', 'locations'] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={tab === t}
            className={`admin-btn ${tab === t ? 'admin-btn--primary' : ''}`}
            onClick={() => setTab(t)}
          >
            {t === 'profiles' && 'Access Profiles'}
            {t === 'mappings' && 'Visitor Type Mapping'}
            {t === 'printers' && 'Printers'}
            {t === 'locations' && 'Location Config'}
          </button>
        ))}
      </div>

      {tab === 'profiles' && (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr><th>Name</th><th>Location</th><th>Provider Ref</th><th>Active</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {profiles.map((p) => (
                <tr key={p.id}>
                  <td>{p.name}</td>
                  <td>{locations.find((l) => l.id === p.location_id)?.name ?? p.location_id}</td>
                  <td>{p.provider_external_profile_ref}</td>
                  <td>{p.is_active ? 'Yes' : 'No'}</td>
                  <td>
                    {canManageAccess && p.is_active && (
                      <>
                        <button type="button" className="admin-btn admin-btn--sm" onClick={() => openEditProfile(p)}>Edit</button>
                        <button type="button" className="admin-btn admin-btn--sm" onClick={() => setDeactivateProfileId(p.id)}>Deactivate</button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'mappings' && (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr><th>Visitor Type</th><th>Profile</th><th>Location</th><th>Active</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {mappings.map((m) => (
                <tr key={m.id}>
                  <td>{m.visitor_type_name}</td>
                  <td>{m.access_profile_name}</td>
                  <td>{locations.find((l) => l.id === m.location_id)?.name ?? m.location_id}</td>
                  <td>{m.is_active ? 'Yes' : 'No'}</td>
                  <td>
                    {canManageAccess && m.is_active && (
                      <>
                        <button type="button" className="admin-btn admin-btn--sm" onClick={() => openEditMapping(m)}>Change</button>
                        <button type="button" className="admin-btn admin-btn--sm" onClick={() => deactivateMapping(m.id)}>Deactivate</button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'printers' && (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr><th>Name</th><th>Location</th><th>Default</th><th>Active</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {printers.map((p) => (
                <tr key={p.id}>
                  <td>{p.name}</td>
                  <td>{locations.find((l) => l.id === p.location_id)?.name ?? p.location_id}</td>
                  <td>{p.is_default ? 'Yes' : 'No'}</td>
                  <td>{p.is_active ? 'Yes' : 'No'}</td>
                  <td>
                    {canManagePrinter && p.is_active && (
                      <>
                        <button type="button" className="admin-btn admin-btn--sm" onClick={() => openEditPrinter(p)}>Edit</button>
                        {!p.is_default && (
                          <button type="button" className="admin-btn admin-btn--sm" onClick={async () => {
                            await api.setDefaultBadgePrinter(p.id);
                            showToast('Default printer updated');
                            await load();
                          }}>Set default</button>
                        )}
                        <button type="button" className="admin-btn admin-btn--sm" onClick={() => setDeactivatePrinterId(p.id)}>Deactivate</button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'locations' && (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr><th>Location</th><th>Enabled</th><th>Grace (min)</th><th>Max (min)</th><th>Default Profile</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {locationConfigs.map((c) => (
                <tr key={c.id}>
                  <td>{c.location_name}</td>
                  <td>{c.access_control_enabled ? 'Yes' : 'No'}</td>
                  <td>{c.credential_grace_minutes}</td>
                  <td>{c.max_credential_duration_minutes}</td>
                  <td>{c.default_access_profile_id ?? '—'}</td>
                  <td>
                    {canManageAccess && (
                      <button type="button" className="admin-btn admin-btn--sm" onClick={() => openEditLocation(c)}>Configure</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!canManageAccess && !canManagePrinter && (
        <p style={{ fontSize: '0.875rem', color: 'var(--color-slate-500)', marginTop: '1rem' }}>
          Read-only configuration view.
        </p>
      )}

      {profileFormOpen && canManageAccess && (
        <div className="admin-card" style={{ marginTop: '1rem' }}>
          <h2 style={{ margin: '0 0 1rem', fontSize: '1rem' }}>{editingProfile ? 'Edit Access Profile' : 'Create Access Profile'}</h2>
          {profileFormError && <p className="login-card__error" role="alert">{profileFormError}</p>}
          <div className="admin-form-grid">
            {!editingProfile && (
              <label>
                Location
                <select className="admin-input" value={profileLocationId} onChange={(e) => setProfileLocationId(Number(e.target.value))}>
                  {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
                </select>
              </label>
            )}
            <label>
              Profile name
              <input className="admin-input" value={profileName} onChange={(e) => setProfileName(e.target.value)} />
            </label>
            <label>
              Description
              <input className="admin-input" value={profileDescription} onChange={(e) => setProfileDescription(e.target.value)} />
            </label>
            <label>
              Provider profile reference
              <input className="admin-input" value={profileRef} onChange={(e) => setProfileRef(e.target.value)} />
            </label>
          </div>
          <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem' }}>
            <button type="button" className="admin-btn admin-btn--primary" disabled={profileSaving} onClick={saveProfile}>
              {profileSaving ? 'Saving…' : 'Save'}
            </button>
            <button type="button" className="admin-btn" onClick={() => setProfileFormOpen(false)}>Cancel</button>
          </div>
        </div>
      )}

      {mappingFormOpen && canManageAccess && (
        <div className="admin-card" style={{ marginTop: '1rem' }}>
          <h2 style={{ margin: '0 0 1rem', fontSize: '1rem' }}>{editingMapping ? 'Change Mapping' : 'Create Mapping'}</h2>
          {mappingFormError && <p className="login-card__error" role="alert">{mappingFormError}</p>}
          <div className="admin-form-grid">
            {!editingMapping && (
              <>
                <label>
                  Location
                  <select className="admin-input" value={mappingLocationId} onChange={(e) => setMappingLocationId(Number(e.target.value))}>
                    {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
                  </select>
                </label>
                <label>
                  Visitor type
                  <select className="admin-input" value={mappingVisitorTypeId} onChange={(e) => setMappingVisitorTypeId(Number(e.target.value))}>
                    {visitorTypes.map((vt) => <option key={vt.id} value={vt.id}>{vt.name}</option>)}
                  </select>
                </label>
              </>
            )}
            <label>
              Access profile
              <select className="admin-input" value={mappingProfileId} onChange={(e) => setMappingProfileId(Number(e.target.value))}>
                {profilesForLocation(editingMapping?.location_id ?? mappingLocationId).map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </label>
          </div>
          <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem' }}>
            <button type="button" className="admin-btn admin-btn--primary" disabled={mappingSaving} onClick={saveMapping}>
              {mappingSaving ? 'Saving…' : 'Save'}
            </button>
            <button type="button" className="admin-btn" onClick={() => setMappingFormOpen(false)}>Cancel</button>
          </div>
        </div>
      )}

      {printerFormOpen && canManagePrinter && (
        <div className="admin-card" style={{ marginTop: '1rem' }}>
          <h2 style={{ margin: '0 0 1rem', fontSize: '1rem' }}>{editingPrinter ? 'Edit Printer' : 'Add Printer'}</h2>
          {printerFormError && <p className="login-card__error" role="alert">{printerFormError}</p>}
          <div className="admin-form-grid">
            {!editingPrinter && (
              <label>
                Location
                <select className="admin-input" value={printerLocationId} onChange={(e) => setPrinterLocationId(Number(e.target.value))}>
                  {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
                </select>
              </label>
            )}
            <label>
              Printer name
              <input className="admin-input" value={printerName} onChange={(e) => setPrinterName(e.target.value)} />
            </label>
            {!editingPrinter && (
              <label>
                Provider
                <select className="admin-input" value={printerProvider} onChange={(e) => setPrinterProvider(e.target.value)}>
                  <option value="dev_mock">Dev Mock (Development)</option>
                  <option value="disabled">Disabled</option>
                </select>
              </label>
            )}
            <label>
              Provider printer reference
              <input className="admin-input" value={printerRef} onChange={(e) => setPrinterRef(e.target.value)} />
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <input type="checkbox" checked={printerDefault} onChange={(e) => setPrinterDefault(e.target.checked)} />
              Set as default
            </label>
          </div>
          <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem' }}>
            <button type="button" className="admin-btn admin-btn--primary" disabled={printerSaving} onClick={savePrinter}>
              {printerSaving ? 'Saving…' : 'Save'}
            </button>
            <button type="button" className="admin-btn" onClick={() => setPrinterFormOpen(false)}>Cancel</button>
          </div>
        </div>
      )}

      {editingLocationId !== null && canManageAccess && (
        <div className="admin-card" style={{ marginTop: '1rem' }}>
          <h2 style={{ margin: '0 0 1rem', fontSize: '1rem' }}>Location access configuration</h2>
          {locFormError && <p className="login-card__error" role="alert">{locFormError}</p>}
          <div className="admin-form-grid">
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <input type="checkbox" checked={locEnabled} onChange={(e) => setLocEnabled(e.target.checked)} />
              Access control enabled
            </label>
            <label>
              Grace minutes
              <input type="number" className="admin-input" min={0} value={locGrace} onChange={(e) => setLocGrace(Number(e.target.value))} />
            </label>
            <label>
              Max credential duration (minutes)
              <input type="number" className="admin-input" min={15} value={locMax} onChange={(e) => setLocMax(Number(e.target.value))} />
            </label>
            <label>
              Default access profile
              <select className="admin-input" value={locDefaultProfileId} onChange={(e) => setLocDefaultProfileId(e.target.value === '' ? '' : Number(e.target.value))}>
                <option value="">None</option>
                {profilesForLocation(editingLocationId).map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </label>
          </div>
          <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem' }}>
            <button type="button" className="admin-btn admin-btn--primary" disabled={locSaving} onClick={() => saveLocationConfig()}>
              {locSaving ? 'Saving…' : 'Save'}
            </button>
            <button type="button" className="admin-btn" onClick={() => setEditingLocationId(null)}>Cancel</button>
          </div>
        </div>
      )}

      {enableConfirmLocationId !== null && (
        <div className="admin-card" style={{ marginTop: '1rem' }}>
          <p>Enable physical access provisioning for {locName}?</p>
          <p style={{ fontSize: '0.875rem', color: 'var(--color-slate-600)' }}>
            Successful visitor check-ins may create temporary access credentials.
          </p>
          <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem' }}>
            <button type="button" className="admin-btn admin-btn--primary" onClick={() => saveLocationConfig(true)}>Enable</button>
            <button type="button" className="admin-btn" onClick={() => setEnableConfirmLocationId(null)}>Cancel</button>
          </div>
        </div>
      )}

      {deactivateProfileId !== null && (
        <div className="admin-card" style={{ marginTop: '1rem' }}>
          <p>Deactivate this access profile? Existing active credentials will remain until expiry.</p>
          <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem' }}>
            <button type="button" className="admin-btn admin-btn--primary" onClick={confirmDeactivateProfile}>Deactivate</button>
            <button type="button" className="admin-btn" onClick={() => setDeactivateProfileId(null)}>Cancel</button>
          </div>
        </div>
      )}

      {deactivatePrinterId !== null && (
        <div className="admin-card" style={{ marginTop: '1rem' }}>
          <p>Deactivate this printer? Queued jobs may require manual action.</p>
          <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem' }}>
            <button type="button" className="admin-btn admin-btn--primary" onClick={confirmDeactivatePrinter}>Deactivate</button>
            <button type="button" className="admin-btn" onClick={() => setDeactivatePrinterId(null)}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}
