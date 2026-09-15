import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from '../components/admin/Sidebar';
import { TopBar } from '../components/admin/TopBar';
import { PreferencesProvider, usePreferences } from '../contexts/PreferencesContext';
import type { UserProfile } from '../types';
import '../styles/admin.css';
import '../styles/theme.css';
import '../styles/vms-staff-ui.css';
import '../styles/vms-reference-shell.css';
import '../styles/vms-enrichment.css';

interface AdminLayoutProps {
  user: UserProfile;
}

function AdminLayoutShell({ user }: AdminLayoutProps) {
  const [collapsed, setCollapsed] = useState(false);
  const { resolvedTheme, preferences } = usePreferences();

  return (
    <div
      className="admin-layout"
      data-theme={resolvedTheme}
      data-density={preferences.density}
      data-reduced-motion={preferences.reducedMotion ? 'true' : undefined}
    >
      <Sidebar
        userId={user.id}
        permissions={user.permissions}
        collapsed={collapsed}
        onToggle={() => setCollapsed((c) => !c)}
      />
      <div className="admin-main">
        <TopBar
          user={user}
          showMenuButton
          onMenuToggle={() => setCollapsed((c) => !c)}
        />
        <main className="admin-content" id="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export function AdminLayout({ user }: AdminLayoutProps) {
  return (
    <PreferencesProvider user={user}>
      <AdminLayoutShell user={user} />
    </PreferencesProvider>
  );
}
