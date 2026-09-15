import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const page = readFileSync(resolve(root, 'pages/locations/LocationsPage.tsx'), 'utf8');
const styles = readFileSync(resolve(root, 'styles/locations-page.css'), 'utf8');

describe('Locations management page', () => {
  it('includes add location and manage access for managers', () => {
    expect(page).toContain('+ Add Location');
    expect(page).toContain('Manage Access');
    expect(page).toContain('locations.manage');
    expect(page).toContain('+ Add Site User');
  });

  it('restricts site staff roles to SITE_ADMIN and SECURITY', () => {
    expect(page).toContain('SITE_ADMIN');
    expect(page).toContain('SECURITY');
    expect(page).not.toContain('GLOBAL_ADMIN');
    expect(page).not.toContain('HEAD_ADMIN');
  });

  it('renders site staff role badges', () => {
    expect(page).toContain('SiteStaffBadges');
    expect(page).toContain('loc-staff-badge--site-admin');
    expect(page).toContain('loc-staff-badge--security');
    expect(page).toContain('loc-staff-badge--empty');
    expect(page).toContain('No staff assigned');
    expect(styles).toContain('.loc-staff-badge--site-admin');
    expect(styles).toContain('.loc-staff-badge--security');
  });

  it('uses correct singular and plural site admin labels', () => {
    expect(page).toContain('1 Site Admin');
    expect(page).toContain('Site Admins');
    expect(page).toContain('formatSecurityLabel');
  });

  it('includes polished add location modal structure', () => {
    expect(page).toContain('loc-add-modal');
    expect(page).toContain('role="dialog"');
    expect(page).toContain('aria-modal="true"');
    expect(page).toContain('id="loc-name"');
    expect(page).toContain('id="loc-code"');
    expect(page).toContain('id="loc-timezone"');
    expect(page).toContain('loc-toggle');
    expect(page).toContain('Create Location');
    expect(page).toContain('admin-btn--secondary');
    expect(page).toContain('Creating…');
  });

  it('includes delete location flow for managers', () => {
    expect(page).toContain('DeleteLocationModal');
    expect(page).toContain('admin-btn--danger-outline');
    expect(page).toContain('Delete Location');
    expect(page).toContain('locationRetireSummary');
    expect(page).toContain('retireLocation');
    expect(page).toContain('loc-delete-summary');
  });

  it('includes remove assignment confirmation', () => {
    expect(page).toContain('Remove access to');
    expect(page).toContain('Remove Access');
  });
});
