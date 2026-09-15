import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const photo = readFileSync(resolve(root, 'components/register-visitor/PhotoCapture.tsx'), 'utf8');
const hook = readFileSync(resolve(root, 'components/register-visitor/useVisitorPhoto.ts'), 'utf8');
const page = readFileSync(resolve(root, 'pages/register-visitor/RegisterVisitorPage.tsx'), 'utf8');
const css = readFileSync(resolve(root, 'styles/register-visitor.css'), 'utf8');

describe('Register Visitor photo capture', () => {
  it('has dedicated photo preview frame', () => {
    expect(photo).toContain('rv-photo-frame');
    expect(photo).toContain('No visitor photo yet');
    expect(css).toContain('.rv-photo-frame');
  });

  it('webcam flow is one-click capture without Use Photo step', () => {
    expect(photo).toContain('Capture Photo');
    expect(photo).not.toContain('Use Photo');
    expect(photo).not.toContain('useCapturedPhoto');
    expect(photo).toContain('rv-webcam-modal');
    expect(photo).toContain('setWebcamOpen(false)');
  });

  it('closes modal only after successful capture staging', () => {
    expect(photo).toContain('await applyPhotoFile');
    expect(page).toContain('stagePhotoFile');
    expect(page).toContain('return true');
    expect(page).toContain('return false');
  });

  it('stops camera tracks on cleanup', () => {
    expect(photo).toContain('getTracks().forEach');
    expect(photo).toContain('t.stop()');
  });

  it('uses single authoritative photo state', () => {
    expect(hook).toContain('VisitorPhotoState');
    expect(hook).toContain('previewUrl');
    expect(hook).toContain('file');
    expect(hook).toContain('mediaId');
  });

  it('supports replace retake and remove actions on main page', () => {
    expect(photo).toContain('Replace Photo');
    expect(photo).toContain('Retake Photo');
    expect(photo).toContain('Remove Photo');
  });

  it('shows capture failure message without silent close', () => {
    expect(photo).toContain('Unable to capture photo. Please try again.');
  });
});

describe('Register Visitor visit tracking summary', () => {
  it('shows read-only actual check-in/out placeholders before submit', () => {
    expect(page).toContain('Visit Tracking');
    expect(page).toContain('Actual Check-In');
    expect(page).toContain('Actual Check-Out');
    expect(page).toContain('Not checked in');
    expect(page).toContain('Not checked out');
    expect(page).toContain('Expected Arrival');
    expect(page).toContain('Expected Departure');
  });
});
