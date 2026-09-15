import type { ReactNode } from 'react';

interface StatePanelProps {
  title: string;
  message?: string;
  action?: { label: string; onClick: () => void };
  children?: ReactNode;
}

export function LoadingState({ message = 'Loading…' }: { message?: string }) {
  return (
    <div className="loading-state" role="status" aria-live="polite">
      <div className="loading-spinner" aria-hidden="true" />
      <span style={{ marginLeft: '0.75rem' }}>{message}</span>
    </div>
  );
}

export function EmptyState({ title, message }: { title: string; message?: string }) {
  return (
    <div className="empty-state">
      <h3 className="empty-state__title">{title}</h3>
      {message && <p className="empty-state__message">{message}</p>}
    </div>
  );
}

export function ErrorState({ title, message, action }: StatePanelProps) {
  return (
    <div className="error-state" role="alert">
      <h3 className="error-state__title">{title}</h3>
      {message && <p className="error-state__message">{message}</p>}
      {action && (
        <button type="button" className="error-state__action" onClick={action.onClick}>
          {action.label}
        </button>
      )}
    </div>
  );
}

export function ComingSoon({ moduleName }: { moduleName: string }) {
  return (
    <div className="coming-soon">
      <span className="coming-soon__badge">Next Phase</span>
      <h2 className="coming-soon__title">{moduleName}</h2>
      <p className="coming-soon__message">
        Coming in the next implementation phase. This foundation shell is ready for future development.
      </p>
    </div>
  );
}

export function NotFoundState() {
  return (
    <ErrorState
      title="Page not found"
      message="The page you are looking for does not exist."
    />
  );
}

export function UnauthorizedState() {
  return (
    <ErrorState
      title="Authentication required"
      message="Please sign in to access the admin area."
    />
  );
}

export function ForbiddenState() {
  return (
    <ErrorState
      title="Access denied"
      message="You do not have permission to view this page."
    />
  );
}
