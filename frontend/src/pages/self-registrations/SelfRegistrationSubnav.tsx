import { NavLink } from 'react-router-dom';

export function SelfRegistrationSubnav() {
  return (
    <nav className="sr-subnav" aria-label="Self registration sections">
      <NavLink
        to="/self-registrations"
        end
        className={({ isActive }) => `sr-subnav__link ${isActive ? 'sr-subnav__link--active' : ''}`}
      >
        Registrations
      </NavLink>
      <NavLink
        to="/self-registrations/qr"
        className={({ isActive }) => `sr-subnav__link ${isActive ? 'sr-subnav__link--active' : ''}`}
      >
        Reception QR
      </NavLink>
    </nav>
  );
}
