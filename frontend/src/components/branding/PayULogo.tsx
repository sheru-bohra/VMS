/** Reuses the same PayU logo asset as the application sidebar (`/payu-logo.jpg`). */
interface PayULogoProps {
  variant?: 'sidebar' | 'auth';
  className?: string;
}

export function PayULogo({ variant = 'auth', className = '' }: PayULogoProps) {
  const rootClass =
    variant === 'sidebar'
      ? `admin-sidebar__logo ${className}`.trim()
      : `login-page__logo ${className}`.trim();
  const imgClass = variant === 'sidebar' ? 'admin-sidebar__logo-img' : 'login-page__logo-img';

  return (
    <div className={rootClass}>
      <img src="/payu-logo.jpg" alt="PayU" className={imgClass} />
    </div>
  );
}
