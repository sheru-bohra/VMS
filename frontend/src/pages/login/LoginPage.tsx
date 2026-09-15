import { useNavigate } from 'react-router-dom';
import { DEV_TEST_USERS } from '../../utils/profileMenuConfig';
import { setDevAuthIdentity } from '../../hooks/useLogout';
import '../../styles/login.css';

export function DevLoginPage() {
  const navigate = useNavigate();

  const continueAsDefault = () => {
    navigate('/');
  };

  const continueAs = (email: string) => {
    setDevAuthIdentity(email);
    window.location.assign('/');
  };

  return (
    <div className="login-page">
      <div className="login-card login-card--wide">
        <h1 className="login-card__title">Visitor Management System</h1>
        <p className="login-card__subtitle">Development authentication is active.</p>
        <p className="login-card__hint">Select a test identity or continue with the default bootstrap owner.</p>

        <button type="button" className="login-card__btn" onClick={continueAsDefault}>
          Continue as default owner
        </button>

        <div className="login-dev-users">
          <p className="login-dev-users__label">Switch test user</p>
          <ul className="login-dev-users__list">
            {DEV_TEST_USERS.map((u) => (
              <li key={u.email}>
                <button type="button" className="login-dev-users__btn" onClick={() => continueAs(u.email)}>
                  {u.label}
                </button>
              </li>
            ))}
          </ul>
        </div>

        <p className="login-card__hint">Visitors do not need to sign in.</p>
      </div>
    </div>
  );
}
