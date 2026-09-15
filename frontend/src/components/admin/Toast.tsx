import { useEffect, useState } from 'react';

interface ToastProps {
  message: string;
  type?: 'success' | 'error';
  onClose: () => void;
}

export function Toast({ message, type = 'success', onClose }: ToastProps) {
  useEffect(() => {
    const t = setTimeout(onClose, 4000);
    return () => clearTimeout(t);
  }, [onClose]);

  const bg = type === 'success' ? '#ecfdf5' : '#fef2f2';
  const color = type === 'success' ? '#047857' : '#b91c1c';
  const border = type === 'success' ? '#a7f3d0' : '#fecaca';

  return (
    <div
      role="status"
      style={{
        position: 'fixed',
        bottom: '1.5rem',
        left: '50%',
        transform: 'translateX(-50%)',
        maxWidth: '90%',
        padding: '0.75rem 1.25rem',
        background: bg,
        color,
        border: `1px solid ${border}`,
        borderRadius: 'var(--radius-md)',
        fontSize: '0.875rem',
        fontWeight: 500,
        boxShadow: 'var(--shadow-md)',
        zIndex: 300,
      }}
    >
      {message}
    </div>
  );
}
