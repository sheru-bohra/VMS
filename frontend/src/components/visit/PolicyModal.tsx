import { useEffect, useState } from 'react';
import { api } from '../../services/api';
import type { VisitorPolicy } from '../../types';

interface PolicyModalProps {
  open: boolean;
  onClose: () => void;
}

export function PolicyModal({ open, onClose }: PolicyModalProps) {
  const [policy, setPolicy] = useState<VisitorPolicy | null>(null);

  useEffect(() => {
    if (!open) return;
    api.publicPolicy().then(setPolicy).catch(() => null);
  }, [open]);

  if (!open) return null;

  return (
    <div className="reg-policy-modal" role="dialog" aria-modal="true" aria-labelledby="policy-title">
      <div className="reg-policy-sheet">
        <h3 id="policy-title">{policy?.title ?? 'Visitor Policy'}</h3>
        <p>{policy?.content ?? 'Loading policy…'}</p>
        <button type="button" className="visitor-btn visitor-btn--primary" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}
