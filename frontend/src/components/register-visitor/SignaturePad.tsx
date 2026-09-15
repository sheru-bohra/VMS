import { useCallback, useEffect, useRef, useState } from 'react';

interface SignaturePadProps {
  onChange: (dataUrl: string | null) => void;
}

export function SignaturePad({ onChange }: SignaturePadProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const drawing = useRef(false);
  const [hasStroke, setHasStroke] = useState(false);

  const getCtx = () => canvasRef.current?.getContext('2d');

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.strokeStyle = 'var(--color-navy-900, #0f172a)';
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
  }, []);

  const emitChange = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    if (!hasStroke) {
      onChange(null);
      return;
    }
    onChange(canvas.toDataURL('image/png'));
  }, [hasStroke, onChange]);

  const start = (x: number, y: number) => {
    const ctx = getCtx();
    if (!ctx) return;
    drawing.current = true;
    ctx.beginPath();
    ctx.moveTo(x, y);
  };

  const move = (x: number, y: number) => {
    if (!drawing.current) return;
    const ctx = getCtx();
    if (!ctx) return;
    ctx.lineTo(x, y);
    ctx.stroke();
    if (!hasStroke) setHasStroke(true);
  };

  const end = () => {
    drawing.current = false;
    emitChange();
  };

  const pointerPos = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    return {
      x: ((e.clientX - rect.left) / rect.width) * canvas.width,
      y: ((e.clientY - rect.top) / rect.height) * canvas.height,
    };
  };

  const clear = () => {
    const canvas = canvasRef.current;
    const ctx = getCtx();
    if (!canvas || !ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    setHasStroke(false);
    onChange(null);
  };

  return (
    <div className="rv-signature-panel">
      <p className="rv-signature-panel__hint">Draw visitor signature if required.</p>
      <canvas
        ref={canvasRef}
        className="rv-signature__canvas"
        width={600}
        height={160}
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture(e.pointerId);
          const { x, y } = pointerPos(e);
          start(x, y);
        }}
        onPointerMove={(e) => {
          const { x, y } = pointerPos(e);
          move(x, y);
        }}
        onPointerUp={end}
        onPointerLeave={end}
        aria-label="Draw signature"
      />
      <button type="button" className="admin-btn admin-btn--outline rv-signature-panel__clear" onClick={clear}>
        Clear Signature
      </button>
    </div>
  );
}
