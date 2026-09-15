import { useCallback, useEffect, useRef, useState } from 'react';

export type VisitorPhotoSource = 'upload' | 'webcam' | null;

export type VisitorPhotoStatus = 'empty' | 'ready' | 'staging' | 'staged' | 'error';

export interface VisitorPhotoState {
  source: VisitorPhotoSource;
  previewUrl: string | null;
  file: File | null;
  mediaId: number | null;
  status: VisitorPhotoStatus;
  error: string | null;
  displayFilename: string | null;
}

const EMPTY: VisitorPhotoState = {
  source: null,
  previewUrl: null,
  file: null,
  mediaId: null,
  status: 'empty',
  error: null,
  displayFilename: null,
};

export function useVisitorPhoto() {
  const [photo, setPhoto] = useState<VisitorPhotoState>(EMPTY);
  const previewRef = useRef<string | null>(null);

  const revokePreview = useCallback((url: string | null) => {
    if (url && url.startsWith('blob:')) {
      URL.revokeObjectURL(url);
    }
  }, []);

  useEffect(() => {
    return () => revokePreview(previewRef.current);
  }, [revokePreview]);

  const setLocalPhoto = useCallback(
    (file: File, source: VisitorPhotoSource) => {
      revokePreview(previewRef.current);
      const url = URL.createObjectURL(file);
      previewRef.current = url;
      setPhoto({
        source,
        previewUrl: url,
        file,
        mediaId: null,
        status: 'ready',
        error: null,
        displayFilename: file.name,
      });
    },
    [revokePreview],
  );

  const markStaging = useCallback(() => {
    setPhoto((p) => (p.file ? { ...p, status: 'staging', error: null } : p));
  }, []);

  const markStaged = useCallback((mediaId: number, storedFilename: string) => {
    setPhoto((p) => ({
      ...p,
      mediaId,
      status: 'staged',
      error: null,
      displayFilename: storedFilename,
    }));
  }, []);

  const markError = useCallback((message: string) => {
    setPhoto((p) => ({ ...p, status: 'error', error: message }));
  }, []);

  const clearPhoto = useCallback(() => {
    revokePreview(previewRef.current);
    previewRef.current = null;
    setPhoto(EMPTY);
  }, [revokePreview]);

  return {
    photo,
    setLocalPhoto,
    markStaging,
    markStaged,
    markError,
    clearPhoto,
  };
}
