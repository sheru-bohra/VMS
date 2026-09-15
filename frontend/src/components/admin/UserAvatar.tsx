import { formatRoleLabel, getInitials } from '../../utils/userDisplay';

interface UserAvatarProps {
  displayName: string | null;
  email: string;
  size?: 'sm' | 'md';
  className?: string;
}

export function UserAvatar({ displayName, email, size = 'md', className }: UserAvatarProps) {
  const initials = getInitials(displayName, email);
  return (
    <div
      className={`user-avatar user-avatar--${size}${className ? ` ${className}` : ''}`}
      aria-hidden="true"
    >
      {initials}
    </div>
  );
}
