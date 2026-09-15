import { Link } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { hasPermission } from '../../utils/permissions';
import type { PermissionKey } from '../../types';
import '../../styles/admin-pages.css';

const ADMIN_MODULES: Array<{
  path: string;
  title: string;
  description: string;
  permission: PermissionKey;
}> = [
  {
    path: '/administration/users',
    title: 'Users & Access',
    description: 'Admin users, roles, and location assignments.',
    permission: 'admins.read',
  },
  {
    path: '/administration/privacy-security',
    title: 'Privacy & Security',
    description: 'Data retention policies and privacy controls.',
    permission: 'privacy.retention.read',
  },
  {
    path: '/administration/access-badges',
    title: 'Access & Badge Administration',
    description: 'Access profiles, badge printers, and integration configuration.',
    permission: 'access.config.read',
  },
  {
    path: '/administration/operations-readiness',
    title: 'Operations & Deployment Readiness',
    description: 'Runtime health, scheduler leases, and release readiness.',
    permission: 'operations.readiness.read',
  },
  {
    path: '/locations',
    title: 'Locations',
    description: 'Site configuration, timezones, and public registration tokens.',
    permission: 'locations.read',
  },
];

export function AdministrationPage() {
  const { user } = useAuth();
  const permissions = user?.permissions ?? [];
  const modules = ADMIN_MODULES.filter((m) => hasPermission(permissions, m.permission));

  return (
    <div className="vms-page-shell">
      <header className="admin-page-header">
        <div>
          <h1 className="admin-page-title">Administration</h1>
          <p className="admin-page-subtitle">Configure users, security, integrations, and platform settings</p>
        </div>
      </header>

      {modules.length === 0 ? (
        <div className="empty-state">
          <h3 className="empty-state__title">No administration modules available</h3>
          <p className="empty-state__message">Your role does not include administration permissions.</p>
        </div>
      ) : (
        <div
          className="admin-card-grid"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: '1rem',
          }}
        >
          {modules.map((mod) => (
            <Link
              key={mod.path}
              to={mod.path}
              className="admin-card"
              style={{
                display: 'block',
                padding: '1.25rem',
                border: '1px solid var(--color-slate-200)',
                borderRadius: '8px',
                textDecoration: 'none',
                color: 'inherit',
                background: 'var(--color-white)',
              }}
            >
              <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: '0 0 0.5rem' }}>{mod.title}</h2>
              <p style={{ fontSize: '0.875rem', color: 'var(--color-slate-500)', margin: 0 }}>{mod.description}</p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
