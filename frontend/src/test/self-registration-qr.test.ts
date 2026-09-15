import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const qrPage = readFileSync(resolve(root, 'pages/self-registrations/SelfRegistrationQrPage.tsx'), 'utf8');
const subnav = readFileSync(resolve(root, 'pages/self-registrations/SelfRegistrationSubnav.tsx'), 'utf8');
const listPage = readFileSync(resolve(root, 'pages/self-registrations/SelfRegistrationsPage.tsx'), 'utf8');
const utils = readFileSync(resolve(root, 'pages/self-registrations/qrRegistrationUtils.ts'), 'utf8');

describe('Reception self-registration QR', () => {
  it('defines reception QR route page', () => {
    expect(qrPage).toContain('SelfRegistrationQrPage');
    expect(qrPage).toContain('Visitor Self Registration QR');
    expect(subnav).toContain('/self-registrations/qr');
    expect(subnav).toContain('Reception QR');
  });

  it('does not mention OTP in how-it-works', () => {
    expect(qrPage.toLowerCase()).not.toContain('otp');
    expect(qrPage.toLowerCase()).not.toContain('sms');
    expect(qrPage.toLowerCase()).not.toContain('mobile otp verified');
  });

  it('refresh does not rotate token client-side', () => {
    expect(qrPage).toContain('registrationUrlRef');
    expect(qrPage).not.toContain('generatePublicToken');
    expect(qrPage).toContain('Refresh QR');
  });

  it('includes reference-aligned controls', () => {
    expect(qrPage).toContain('Fullscreen');
    expect(qrPage).toContain('Download A4 PDF');
    expect(qrPage).toContain('View Pending');
    expect(qrPage).toContain('Copy URL');
    expect(qrPage).toContain('Today&apos;s Stats');
  });

  it('registrations list keeps subnav and site filter param', () => {
    expect(listPage).toContain('SelfRegistrationSubnav');
    expect(listPage).toContain('siteParam');
  });

  it('builds deterministic QR data URL helper', async () => {
    const { qrDataUrl } = await import('../pages/self-registrations/qrRegistrationUtils');
    const url = 'http://localhost:7272/visit/register/test-token';
    const a = await qrDataUrl(url, 128);
    const b = await qrDataUrl(url, 128);
    expect(a).toBe(b);
    expect(a.startsWith('data:image/png')).toBe(true);
  });
});
