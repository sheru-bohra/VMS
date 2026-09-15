import { Outlet } from 'react-router-dom';
import '../styles/visitor.css';

export function VisitorLayout() {
  return (
    <div className="visitor-layout">
      <Outlet />
    </div>
  );
}
