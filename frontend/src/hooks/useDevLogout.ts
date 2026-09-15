import { useNavigate } from 'react-router-dom';
import { clearDevAuthIdentity } from './useLogout';

export function useDevLogout() {
  const navigate = useNavigate();

  return () => {
    clearDevAuthIdentity();
    navigate('/login', { replace: true });
    window.location.assign('/login');
  };
}
