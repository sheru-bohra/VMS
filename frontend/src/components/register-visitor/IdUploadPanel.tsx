interface IdUploadPanelProps {
  fileName: string;
  onFileSelect: (file: File | null) => void;
}

export function IdUploadPanel({ fileName, onFileSelect }: IdUploadPanelProps) {
  return (
    <div className="rv-id-panel">
      <strong>Scan Government ID (Auto-fill)</strong>
      <div className="rv-id-panel__row">
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="rv-id-panel__input"
          onChange={(e) => onFileSelect(e.target.files?.[0] ?? null)}
        />
        {fileName ? (
          <span className="rv-id-panel__filename">{fileName}</span>
        ) : (
          <span className="rv-id-panel__filename rv-id-panel__filename--muted">No file selected</span>
        )}
        {fileName && (
          <button type="button" className="admin-btn admin-btn--ghost" onClick={() => onFileSelect(null)}>
            Remove
          </button>
        )}
      </div>
      <p className="rv-id-panel__note">
        Auto-fill unavailable — enter details manually. OCR is not configured in this environment.
      </p>
    </div>
  );
}
