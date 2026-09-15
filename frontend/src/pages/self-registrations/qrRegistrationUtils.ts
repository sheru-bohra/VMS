/** Utilities for reception self-registration QR (deterministic URL, safe filenames). */

export function sanitizeLocationFilename(name: string): string {
  return name
    .trim()
    .replace(/\s+/g, '_')
    .replace(/[^A-Za-z0-9_-]/g, '')
    .slice(0, 48) || 'Location';
}

export function buildQrPdfFilename(company: string, locationName: string): string {
  const loc = sanitizeLocationFilename(locationName);
  const brand = sanitizeLocationFilename(company) || 'PayU';
  return `${brand}_${loc}_Visitor_Self_Registration_QR.pdf`;
}

export async function qrDataUrl(url: string, size = 320): Promise<string> {
  const QRCode = await import('qrcode');
  return QRCode.toDataURL(url, {
    width: size,
    margin: 2,
    errorCorrectionLevel: 'M',
    color: { dark: '#000000', light: '#ffffff' },
  });
}
