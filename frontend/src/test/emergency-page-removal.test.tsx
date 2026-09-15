import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Navigate, Route, Routes } from 'react-router-dom';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');

describe('Emergency Roll-Call page removal', () => {
  const navigationConfig = readFileSync(resolve(root, 'utils/navigationConfig.ts'), 'utf8');
  const appSource = readFileSync(resolve(root, 'app/App.tsx'), 'utf8');

  it('navigation config does not include Emergency Roll-Call', () => {
    expect(navigationConfig).not.toContain('Emergency Roll-Call');
    expect(navigationConfig).not.toContain('/emergency-roll-call');
  });

  it('App.tsx redirects legacy /emergency-roll-call route to dashboard', () => {
    expect(appSource).toContain('path="emergency-roll-call"');
    expect(appSource).toContain('<Navigate to="/dashboard" replace />');
    expect(appSource).not.toContain('EmergencyRollCallPage');
  });

  it('legacy /emergency-roll-call URL redirects safely', () => {
    render(
      <MemoryRouter initialEntries={['/emergency-roll-call']}>
        <Routes>
          <Route path="emergency-roll-call" element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<div>Visitor Management Dashboard</div>} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('Visitor Management Dashboard')).toBeInTheDocument();
  });
});
