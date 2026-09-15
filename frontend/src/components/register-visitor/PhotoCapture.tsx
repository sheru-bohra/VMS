import { useCallback, useEffect, useRef, useState } from 'react';
import type { VisitorPhotoState } from './useVisitorPhoto';

const MAX_BYTES = 5 * 1024 * 1024;
const ACCEPT = 'image/jpeg,image/png,image/webp';

interface PhotoCaptureProps {
  photo: VisitorPhotoState;
  fullName: string;
  onLocalPhoto: (file: File, source: 'upload' | 'webcam') => Promise<boolean>;
  onClear: () => void;
}

function CameraIcon() {
  return (
    <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <path d="M4 7h3l2-3h6l2 3h3a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2z" />
      <circle cx="12" cy="13" r="3.5" />
    </svg>
  );
}

export function PhotoCapture({ photo, fullName, onLocalPhoto, onClear }: PhotoCaptureProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [webcamOpen, setWebcamOpen] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [capturing, setCapturing] = useState(false);

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => {
    return () => stopStream();
  }, [stopStream]);

  useEffect(() => {
    if (!webcamOpen || !videoRef.current || !streamRef.current) return;
    const video = videoRef.current;
    video.srcObject = streamRef.current;
    video.play().catch(() => {});
  }, [webcamOpen]);

  const applyPhotoFile = async (file: File, source: 'upload' | 'webcam') => {
    if (file.size > MAX_BYTES) {
      setCameraError(`Photo must be under ${MAX_BYTES / (1024 * 1024)} MB.`);
      return false;
    }
    setCameraError(null);
    return onLocalPhoto(file, source);
  };

  const handleUpload = async (file: File | null) => {
    if (!file) return;
    await applyPhotoFile(file, 'upload');
  };

  const openWebcam = async () => {
    setCameraError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } });
      streamRef.current = stream;
      setWebcamOpen(true);
    } catch {
      setCameraError('Camera access was denied. You can upload a photo instead.');
      setWebcamOpen(false);
      stopStream();
    }
  };

  const closeWebcam = () => {
    stopStream();
    setWebcamOpen(false);
  };

  const captureFrame = () => {
    const video = videoRef.current;
    if (!video || capturing) {
      if (!video) setCameraError('Unable to capture photo. Please try again.');
      return;
    }
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      setCameraError('Unable to capture photo. Please try again.');
      return;
    }
    ctx.drawImage(video, 0, 0);
    setCapturing(true);
    setCameraError(null);
    canvas.toBlob(
      async (blob) => {
        try {
          if (!blob) {
            setCameraError('Unable to capture photo. Please try again.');
            return;
          }
          const file = new File([blob], 'webcam-photo.jpg', { type: 'image/jpeg' });
          const ok = await applyPhotoFile(file, 'webcam');
          if (ok) {
            stopStream();
            setWebcamOpen(false);
          } else {
            setCameraError('Unable to capture photo. Please try again.');
          }
        } finally {
          setCapturing(false);
        }
      },
      'image/jpeg',
      0.88,
    );
  };

  const removePhoto = () => {
    if (window.confirm('Remove visitor photo?')) {
      onClear();
    }
  };

  const hasPhoto = Boolean(photo.previewUrl && photo.status !== 'empty');

  return (
    <div className="rv-photo-panel">
      <div className={`rv-photo-frame ${hasPhoto ? 'rv-photo-frame--filled' : ''}`}>
        {hasPhoto ? (
          <img src={photo.previewUrl!} alt="Visitor photo preview" className="rv-photo-frame__img" />
        ) : (
          <div className="rv-photo-frame__empty">
            <CameraIcon />
            <span>No visitor photo yet</span>
          </div>
        )}
      </div>

      {photo.status === 'staging' && <p className="rv-photo-status">Saving photo…</p>}
      {photo.status === 'staged' && <p className="rv-photo-status rv-photo-status--ok">Ready to save</p>}
      {photo.error && <p className="reg-form-error">{photo.error}</p>}
      {cameraError && <p className="reg-form-error">{cameraError}</p>}

      <div className="rv-photo-actions">
        {!hasPhoto ? (
          <>
            <input
              ref={fileRef}
              type="file"
              accept={ACCEPT}
              className="rv-photo__file"
              onChange={(e) => handleUpload(e.target.files?.[0] ?? null)}
            />
            <button type="button" className="admin-btn admin-btn--outline" onClick={() => fileRef.current?.click()}>
              Upload Photo
            </button>
            <button type="button" className="admin-btn admin-btn--outline" onClick={openWebcam}>
              Use Webcam
            </button>
          </>
        ) : (
          <>
            <button type="button" className="admin-btn admin-btn--outline" onClick={openWebcam}>
              Retake Photo
            </button>
            <button type="button" className="admin-btn admin-btn--outline" onClick={() => fileRef.current?.click()}>
              Replace Photo
            </button>
            <button type="button" className="admin-btn admin-btn--ghost-danger" onClick={removePhoto}>
              Remove Photo
            </button>
            <input
              ref={fileRef}
              type="file"
              accept={ACCEPT}
              className="rv-photo__file"
              onChange={(e) => handleUpload(e.target.files?.[0] ?? null)}
            />
          </>
        )}
      </div>

      {webcamOpen && (
        <div className="rv-webcam-modal" role="dialog" aria-modal="true" aria-label="Webcam capture">
          <div className="rv-webcam-modal__sheet">
            <video ref={videoRef} className="rv-webcam-modal__video" muted playsInline autoPlay />
            <div className="rv-webcam-modal__actions">
              <button
                type="button"
                className="admin-btn admin-btn--primary"
                onClick={captureFrame}
                disabled={capturing}
              >
                {capturing ? 'Saving…' : 'Capture Photo'}
              </button>
              <button type="button" className="admin-btn admin-btn--outline" onClick={closeWebcam}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {fullName.trim() && hasPhoto && (
        <p className="rv-photo-hint">Photo will be saved as {fullName.trim().replace(/\s+/g, '_')}_…</p>
      )}
    </div>
  );
}
