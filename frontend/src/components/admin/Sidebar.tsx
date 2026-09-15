import { useCallback, useEffect, useRef, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import type { NavChildConfig, NavGroupConfig } from '../../utils/navigationConfig';
import {
  findActiveChildId,
  findActiveGroupId,
  isNavChildActive,
} from '../../utils/navigationConfig';
import { buildInitialOpenGroupId, saveOpenGroupId } from '../../utils/sidebarGroups';
import { filterDashboardNav, filterNavGroupsByPermissions, filterRegisterVisitorNav } from '../../utils/permissions';
import { usePreferences } from '../../contexts/PreferencesContext';
import { PayULogo } from '../branding/PayULogo';
import { NavIcon } from './NavIcon';

interface SidebarProps {
  userId: number;
  permissions: string[];
  collapsed: boolean;
  onToggle: () => void;
}

function ChevronIcon({ expanded }: { expanded: boolean }) {
  return (
    <svg
      className="admin-sidebar__chevron"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      aria-hidden="true"
    >
      {expanded ? <path d="M6 9l6 6 6-6" /> : <path d="M9 6l6 6-6 6" />}
    </svg>
  );
}

function NavChildLink({
  item,
  collapsed,
  active,
  onNavigate,
}: {
  item: NavChildConfig;
  collapsed: boolean;
  active: boolean;
  onNavigate?: () => void;
}) {
  return (
    <li>
      <NavLink
        to={item.path}
        className={() =>
          `admin-sidebar__link admin-sidebar__link--child ${active ? 'admin-sidebar__link--active' : ''}`
        }
        title={collapsed ? item.label : undefined}
        onClick={onNavigate}
      >
        <NavIcon name={item.icon} tone={item.iconTone} active={active} />
        {!collapsed && <span className="admin-sidebar__label">{item.label}</span>}
      </NavLink>
    </li>
  );
}

function NavGroupSection({
  group,
  collapsed,
  expanded,
  activeGroup,
  activeChildId,
  onToggle,
  onFlyoutOpen,
  flyoutOpen,
  onFlyoutClose,
  reducedMotion,
}: {
  group: NavGroupConfig;
  collapsed: boolean;
  expanded: boolean;
  activeGroup: boolean;
  activeChildId?: string;
  onToggle: () => void;
  onFlyoutOpen: () => void;
  flyoutOpen: boolean;
  onFlyoutClose: () => void;
  reducedMotion: boolean;
}) {
  const panelId = `sidebar-group-${group.id}`;

  const handleGroupClick = () => {
    if (collapsed) {
      onFlyoutOpen();
    } else {
      onToggle();
    }
  };

  return (
    <li
      className={`admin-sidebar__group ${activeGroup ? 'admin-sidebar__group--active-parent' : ''} ${group.id === 'system-administration' ? 'admin-sidebar__group--divider' : ''}`}
    >
      <button
        type="button"
        className="admin-sidebar__group-btn"
        onClick={handleGroupClick}
        aria-expanded={collapsed ? flyoutOpen : expanded}
        aria-controls={panelId}
        title={collapsed ? group.label : undefined}
      >
        <NavIcon name={group.icon} tone={group.iconTone} active={activeGroup} />
        {!collapsed && (
          <>
            <span className="admin-sidebar__group-label">{group.label}</span>
            <ChevronIcon expanded={expanded} />
          </>
        )}
      </button>

      {!collapsed && (
        <ul
          id={panelId}
          className={`admin-sidebar__sublist ${expanded ? 'admin-sidebar__sublist--open' : ''} ${reducedMotion ? 'admin-sidebar__sublist--no-motion' : ''}`}
          hidden={!expanded}
        >
          {group.children.map((child) => (
            <NavChildLink
              key={child.id}
              item={child}
              collapsed={false}
              active={child.id === activeChildId}
            />
          ))}
        </ul>
      )}

      {collapsed && flyoutOpen && (
        <>
          <button
            type="button"
            className="admin-sidebar__flyout-backdrop"
            aria-label="Close menu"
            onClick={onFlyoutClose}
          />
          <div className="admin-sidebar__flyout" role="menu">
            <div className="admin-sidebar__flyout-title">{group.label}</div>
            <ul className="admin-sidebar__flyout-list">
              {group.children.map((child) => (
                <NavChildLink
                  key={child.id}
                  item={child}
                  collapsed={false}
                  active={child.id === activeChildId}
                  onNavigate={onFlyoutClose}
                />
              ))}
            </ul>
          </div>
        </>
      )}
    </li>
  );
}

export function Sidebar({ userId, permissions, collapsed, onToggle }: SidebarProps) {
  const location = useLocation();
  const { preferences } = usePreferences();
  const reducedMotion = preferences.reducedMotion;

  const groups = filterNavGroupsByPermissions(permissions);
  const dashboard = filterDashboardNav(permissions);
  const registerVisitor = filterRegisterVisitorNav(permissions);
  const activeGroupId = findActiveGroupId(location.pathname, groups);
  const activeChildId = findActiveChildId(location.pathname, groups);
  const dashboardActive = dashboard ? isNavChildActive(location.pathname, dashboard) : false;
  const registerVisitorActive = registerVisitor
    ? isNavChildActive(location.pathname, registerVisitor)
    : false;

  const [openGroupId, setOpenGroupId] = useState<string | null>(() =>
    buildInitialOpenGroupId(userId, activeGroupId),
  );
  const [flyoutGroupId, setFlyoutGroupId] = useState<string | null>(null);
  const prevPathRef = useRef(location.pathname);

  useEffect(() => {
    if (location.pathname === prevPathRef.current) return;
    prevPathRef.current = location.pathname;

    if (activeGroupId) {
      setOpenGroupId(activeGroupId);
      saveOpenGroupId(userId, activeGroupId);
      return;
    }

    if (dashboardActive || registerVisitorActive) {
      setOpenGroupId(null);
      saveOpenGroupId(userId, null);
    }
  }, [location.pathname, activeGroupId, dashboardActive, registerVisitorActive, userId]);

  useEffect(() => {
    if (!collapsed) setFlyoutGroupId(null);
  }, [collapsed]);

  const toggleGroup = useCallback(
    (groupId: string) => {
      setOpenGroupId((prev) => {
        const next = prev === groupId ? null : groupId;
        saveOpenGroupId(userId, next);
        return next;
      });
    },
    [userId],
  );

  return (
    <aside className={`admin-sidebar ${collapsed ? 'admin-sidebar--collapsed' : ''}`} aria-label="Main navigation">
      <div className="admin-sidebar__brand">
        <PayULogo variant="sidebar" />
        {!collapsed && (
          <div className="admin-sidebar__brand-text">
            <span className="admin-sidebar__title">Visitor Management</span>
            <span className="admin-sidebar__brand-subtitle">PayU Workplace</span>
          </div>
        )}
      </div>

      <nav className="admin-sidebar__nav">
        <ul className="admin-sidebar__list">
          {!collapsed && <li className="admin-sidebar__nav-label">MAIN</li>}
          {dashboard && (
            <li>
              <NavLink
                to={dashboard.path}
                className={() =>
                  `admin-sidebar__link ${dashboardActive ? 'admin-sidebar__link--active' : ''}`
                }
                title={collapsed ? dashboard.label : undefined}
              >
                <NavIcon name={dashboard.icon} tone={dashboard.iconTone} active={dashboardActive} />
                {!collapsed && <span className="admin-sidebar__label">{dashboard.label}</span>}
              </NavLink>
            </li>
          )}

          {registerVisitor && (
            <li>
              <NavLink
                to={registerVisitor.path}
                className={() =>
                  `admin-sidebar__link ${registerVisitorActive ? 'admin-sidebar__link--active' : ''}`
                }
                title={collapsed ? registerVisitor.label : undefined}
              >
                <NavIcon
                  name={registerVisitor.icon}
                  tone={registerVisitor.iconTone}
                  active={registerVisitorActive}
                />
                {!collapsed && <span className="admin-sidebar__label">{registerVisitor.label}</span>}
              </NavLink>
            </li>
          )}

          {groups.map((group) => (
            <NavGroupSection
              key={group.id}
              group={group}
              collapsed={collapsed}
              expanded={openGroupId === group.id}
              activeGroup={group.id === activeGroupId}
              activeChildId={activeChildId}
              onToggle={() => toggleGroup(group.id)}
              onFlyoutOpen={() => setFlyoutGroupId(group.id)}
              flyoutOpen={flyoutGroupId === group.id}
              onFlyoutClose={() => setFlyoutGroupId(null)}
              reducedMotion={reducedMotion}
            />
          ))}
        </ul>
      </nav>

      <button
        type="button"
        className="admin-sidebar__toggle"
        onClick={onToggle}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {collapsed ? '»' : '«'}
      </button>
    </aside>
  );
}
