import type { ReactNode } from 'react';
import { NavIcon } from '../admin/NavIcon';
import type { NavIconName, NavIconTone } from '../../utils/navigationConfig';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  icon?: NavIconName;
  iconTone?: NavIconTone;
  actions?: ReactNode;
}

export function PageHeader({
  title,
  subtitle,
  icon = 'layout-dashboard',
  iconTone = 'indigo',
  actions,
}: PageHeaderProps) {
  return (
    <header className="vms-page-header">
      <div className="vms-page-header__title-row">
        <NavIcon name={icon} tone={iconTone} className="vms-page-header__icon" />
        <div>
          <h1 className="vms-page-header__title">{title}</h1>
          {subtitle ? <p className="vms-page-header__subtitle">{subtitle}</p> : null}
        </div>
      </div>
      {actions ? <div className="vms-page-header__actions">{actions}</div> : null}
    </header>
  );
}
