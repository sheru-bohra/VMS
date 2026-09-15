import type { UserProfile } from '../../types';
import { ProfileMenu } from './ProfileMenu';
import '../../styles/profile-menu.css';

interface TopBarProps {
  user: UserProfile;
  onMenuToggle?: () => void;
  showMenuButton?: boolean;
}

export function TopBar({ user, onMenuToggle, showMenuButton }: TopBarProps) {
  return (
    <header className="admin-topbar">
      <div className="admin-topbar__left">
        {showMenuButton && (
          <button
            type="button"
            className="admin-topbar__menu-btn"
            onClick={onMenuToggle}
            aria-label="Toggle navigation menu"
          >
            ☰
          </button>
        )}
        <h1 className="admin-topbar__product-title">PayU Visitor Management</h1>
      </div>
      <div className="admin-topbar__spacer" />
      <ProfileMenu user={user} />
    </header>
  );
}
