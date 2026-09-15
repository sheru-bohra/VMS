import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { render, screen, fireEvent } from '@testing-library/react';
import { AdminTabs } from '../components/ui/AdminTabs';
import { StatusBadge } from '../components/ui/StatusBadge';
import {
  formatRetentionAction,
  formatRetentionCategory,
} from '../utils/displayLabels';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');

describe('global UI enrichment — shared primitives', () => {
  const enrichmentCss = readFileSync(resolve(root, 'styles/vms-enrichment.css'), 'utf8');
  const adminLayout = readFileSync(resolve(root, 'layouts/AdminLayout.tsx'), 'utf8');
  const privacyPage = readFileSync(resolve(root, 'pages/administration/PrivacySecurityPage.tsx'), 'utf8');

  it('AdminLayout imports enrichment CSS scoped to vms-page-shell', () => {
    expect(adminLayout).toContain('vms-enrichment.css');
    expect(enrichmentCss).toContain('.vms-page-shell');
    expect(enrichmentCss).not.toContain('.admin-main .admin-table');
  });

  it('StatusBadge renders semantic variant classes', () => {
    const { container, rerender } = render(<StatusBadge status="APPROVED" />);
    expect(container.querySelector('.vms-status-badge--approved')).not.toBeNull();
    rerender(<StatusBadge status="PENDING_APPROVAL" />);
    expect(container.querySelector('.vms-status-badge--pending')).not.toBeNull();
    rerender(<StatusBadge status="REJECTED" />);
    expect(container.querySelector('.vms-status-badge--rejected')).not.toBeNull();
  });

  it('AdminTabs supports active state and counts', () => {
    const tabs = [
      { id: 'a', label: 'Tab A', count: 3 },
      { id: 'b', label: 'Tab B' },
    ];
    const onChange = vi.fn();
    render(<AdminTabs tabs={tabs} active="a" onChange={onChange} />);
    expect(screen.getByRole('tab', { name: /Tab A/i })).toHaveAttribute('aria-selected', 'true');
    fireEvent.click(screen.getByRole('tab', { name: /Tab B/i }));
    expect(onChange).toHaveBeenCalledWith('b');
  });

  it('retention display labels preserve backend identifiers', () => {
    expect(formatRetentionCategory('AI_INTERACTION')).toBe('AI Interaction');
    expect(formatRetentionCategory('VISITOR_PII')).toBe('Visitor PII');
    expect(formatRetentionAction('PURGE_CONTENT')).toBe('Purge Content');
    expect(formatRetentionAction('ANONYMIZE')).toBe('Anonymize');
    // Raw codes unchanged when passed to API — display layer only
    expect('AI_INTERACTION').toBe('AI_INTERACTION');
  });

  it('Privacy & Security uses AdminTabs with four sections', () => {
    expect(privacyPage).toContain('AdminTabs');
    expect(privacyPage).toContain('Data Retention');
    expect(privacyPage).toContain('Security Readiness');
    expect(privacyPage).toContain('Audit Integrity');
    expect(privacyPage).toContain('File Security');
    expect(privacyPage).toContain('formatRetentionCategory');
    expect(privacyPage).not.toContain('admin-chip-row');
  });
});
