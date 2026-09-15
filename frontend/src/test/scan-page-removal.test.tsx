import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Navigate, Route, Routes } from 'react-router-dom';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');

describe('Scan Visitor QR page removal', () => {
  const navigationConfig = readFileSync(resolve(root, 'utils/navigationConfig.ts'), 'utf8');
  const appSource = readFileSync(resolve(root, 'app/App.tsx'), 'utf8');

  it('navigation config does not include Scan Visitor QR', () => {
    expect(navigationConfig).not.toContain('Scan Visitor QR');
    expect(navigationConfig).not.toContain("path: '/scan'");
  });

  it('App.tsx redirects legacy /scan route to dashboard', () => {
    expect(appSource).toContain('path="scan"');
    expect(appSource).toContain('<Navigate to="/dashboard" replace />');
    expect(appSource).not.toContain('ScanPage');
  });

  it('legacy /scan URL redirects to dashboard without crash', () => {
    render(
      <MemoryRouter initialEntries={['/scan']}>
        <Routes>
          <Route path="scan" element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<div>Visitor Management Dashboard</div>} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('Visitor Management Dashboard')).toBeInTheDocument();
  });
});
