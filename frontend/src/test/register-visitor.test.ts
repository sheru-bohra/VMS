import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const page = readFileSync(resolve(root, 'pages/register-visitor/RegisterVisitorPage.tsx'), 'utf8');

describe('Register Visitor page', () => {
  it('maps review purpose and visit date to correct fields', () => {
    expect(page).toContain('htmlFor="field-purpose">Purpose *</label>');
    expect(page).toContain('htmlFor="field-visitDate">Visit Date *</label>');
    expect(page).toContain('purpose.trim()');
    expect(page).toContain('visitDate');
  });

  it('requires policy acceptance before submit', () => {
    expect(page).toContain('policy_accepted: policyAccepted');
    expect(page).toContain('policyAccepted');
  });

  it('uses existing createInvitation API', () => {
    expect(page).toContain('api.createInvitation');
    expect(page).toContain('ApiClientError');
    expect(page).toContain('formatSubmitError');
    expect(page).toContain('photo_media_id');
    expect(page).toContain('triggerOperationalRefresh');
  });

  it('includes visit tracking summary on review step', () => {
    expect(page).toContain('Visit Tracking');
    expect(page).toContain('Not checked in');
    expect(page).toContain('Not checked out');
  });
});
