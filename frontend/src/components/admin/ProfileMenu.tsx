import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMsal } from '@azure/msal-react';
import type { UserProfile } from '../../types';
import { isDevAuthMode, isEntraAuthMode } from '../../config/auth';
import { usePreferences } from '../../contexts/PreferencesContext';
import { formatRoleLabel } from '../../utils/userDisplay';
import { getProfileAdminLinks, DEV_TEST_USERS } from '../../utils/profileMenuConfig';
import { UserAvatar } from './UserAvatar';
import { useDevLogout } from '../../hooks/useDevLogout';
import { performEntraLogout } from '../../hooks/useLogout';
import type { ThemePreference } from '../../utils/userPreferences';

interface ProfileMenuProps {
  user: UserProfile;
}

function ProfileMenuContent({ user, onLogout }: ProfileMenuProps & { onLogout: () => void }) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [themeOpen, setThemeOpen] = useState(false);
  const [devOpen, setDevOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const { preferences, setTheme } = usePreferences();

  const displayName = user.display_name ?? user.email.split('@')[0];
  const adminLinks = getProfileAdminLinks(user.permissions);

  const close = useCallback(() => {
    setOpen(false);
    setThemeOpen(false);
    setDevOpen(false);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    const onPointerDown = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        menuRef.current?.contains(target) ||
        triggerRef.current?.contains(target)
      ) {
        return;
      }
      close();
    };
    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('mousedown', onPointerDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.removeEventListener('mousedown', onPointerDown);
    };
  }, [open, close]);

  useEffect(() => {
    if (!open) return;
    const main = document.getElementById('main-content');
    const prevOverflow = main?.style.overflow ?? '';
    if (main) {
      main.style.overflow = 'hidden';
    }
    return () => {
      if (main) {
        main.style.overflow = prevOverflow;
      }
    };
  }, [open]);

  const toggleOpen = () => setOpen((v) => !v);

  const onThemeSelect = (theme: ThemePreference) => {
    setTheme(theme);
    setThemeOpen(false);
  };

  const themeOptions: Array<{ id: ThemePreference; label: string }> = [
    { id: 'system', label: 'System' },
    { id: 'light', label: 'Light' },
    { id: 'dark', label: 'Dark' },
  ];

  return (
    <div className="profile-menu">
      <button
        ref={triggerRef}
        type="button"
        className="profile-menu__trigger"
        onClick={toggleOpen}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label="Account menu"
      >
        <div className="profile-menu__trigger-text">
          <span className="profile-menu__trigger-name" title={displayName}>{displayName}</span>
          <span className="profile-menu__trigger-role">{formatRoleLabel(user.role)}</span>
        </div>
        <UserAvatar displayName={user.display_name} email={user.email} size="sm" />
        <span className="profile-menu__chevron" aria-hidden="true">▾</span>
      </button>

      {open && (
        <div ref={menuRef} className="profile-menu__dropdown" role="menu">
          <div className="profile-menu__header">
            <UserAvatar displayName={user.display_name} email={user.email} />
            <div className="profile-menu__header-text">
              <div className="profile-menu__header-name" title={displayName}>{displayName}</div>
              <div className="profile-menu__header-email" title={user.email}>{user.email}</div>
              <div className="profile-menu__header-meta">
                <span>{formatRoleLabel(user.role)}</span>
                {user.is_owner && <span className="profile-menu__badge">Owner</span>}
              </div>
            </div>
          </div>

          <div className="profile-menu__section">
            <div className="profile-menu__section-label">Account</div>
            <button type="button" className="profile-menu__item" role="menuitem" onClick={() => { navigate('/profile'); close(); }}>
              My Profile
            </button>
            <button type="button" className="profile-menu__item" role="menuitem" onClick={() => { navigate('/profile#access'); close(); }}>
              My Access
            </button>
          </div>

          <div className="profile-menu__section">
            <div className="profile-menu__section-label">Preferences</div>
            <button type="button" className="profile-menu__item" role="menuitem" onClick={() => { navigate('/preferences'); close(); }}>
              Preferences
            </button>
            <div className="profile-menu__submenu">
              <button
                type="button"
                className="profile-menu__item profile-menu__item--submenu"
                aria-expanded={themeOpen}
                onClick={() => setThemeOpen((v) => !v)}
              >
                Appearance
                <span className="profile-menu__chevron-sm" aria-hidden="true">▾</span>
              </button>
              {themeOpen && (
                <div className="profile-menu__submenu-panel">
                  {themeOptions.map((opt) => (
                    <button
                      key={opt.id}
                      type="button"
                      className="profile-menu__subitem"
                      onClick={() => onThemeSelect(opt.id)}
                    >
                      {opt.label}
                      {preferences.theme === opt.id && <span className="profile-menu__check">✓</span>}
                    </button>
                  ))}
                  <button
                    type="button"
                    className="profile-menu__subitem profile-menu__subitem--link"
                    onClick={() => { navigate('/preferences#appearance'); close(); }}
                  >
                    More appearance settings…
                  </button>
                </div>
              )}
            </div>
          </div>

          {adminLinks.length > 0 && (
            <div className="profile-menu__section">
              <div className="profile-menu__section-label">Administration</div>
              {adminLinks.map((link) => (
                <button
                  key={link.path}
                  type="button"
                  className="profile-menu__item"
                  role="menuitem"
                  onClick={() => { navigate(link.path); close(); }}
                >
                  {link.label}
                </button>
              ))}
            </div>
          )}

          {isDevAuthMode && (
            <div className="profile-menu__section profile-menu__section--dev">
              <div className="profile-menu__section-label">Developer</div>
              <button
                type="button"
                className="profile-menu__item profile-menu__item--submenu"
                aria-expanded={devOpen}
                onClick={() => setDevOpen((v) => !v)}
              >
                Switch Test User
                <span className="profile-menu__chevron-sm" aria-hidden="true">▾</span>
              </button>
              {devOpen && (
                <div className="profile-menu__submenu-panel">
                  {DEV_TEST_USERS.map((u) => (
                    <button
                      key={u.email}
                      type="button"
                      className="profile-menu__subitem"
                      onClick={() => {
                        localStorage.setItem('vms_dev_user', u.email);
                        window.location.assign('/');
                      }}
                    >
                      {u.label}
                      {user.email === u.email && <span className="profile-menu__check">✓</span>}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="profile-menu__section profile-menu__section--footer">
            <button type="button" className="profile-menu__item profile-menu__item--danger" role="menuitem" onClick={onLogout}>
              Sign Out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function ProfileMenuDev({ user }: ProfileMenuProps) {
  const devLogout = useDevLogout();
  return <ProfileMenuContent user={user} onLogout={devLogout} />;
}

function ProfileMenuEntra({ user }: ProfileMenuProps) {
  const { instance } = useMsal();
  const navigate = useNavigate();
  const onLogout = () => {
    performEntraLogout(instance, user.auth_provider, navigate);
  };
  return <ProfileMenuContent user={user} onLogout={onLogout} />;
}

export function ProfileMenu({ user }: ProfileMenuProps) {
  if (isEntraAuthMode) {
    return <ProfileMenuEntra user={user} />;
  }
  return <ProfileMenuDev user={user} />;
}
