import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { VisitorActivityChart } from '../components/dashboard/VisitorActivityChart';

describe('Visitor Activity chart', () => {
  it('shows empty state when all series are zero', () => {
    render(
      <VisitorActivityChart
        points={[
          { date: '2026-08-27', label: '27', expected: 0, checked_in: 0, checked_out: 0 },
        ]}
      />,
    );
    expect(screen.getByText('No visitor activity for the selected period.')).toBeInTheDocument();
    expect(screen.queryByText('27')).not.toBeInTheDocument();
  });

  it('renders chart SVG when activity exists', () => {
    const { container } = render(
      <VisitorActivityChart
        points={[
          { date: '2026-08-27T09:00:00+00:00', label: '09:00', expected: 1, checked_in: 2, checked_out: 1 },
          { date: '2026-08-27T10:00:00+00:00', label: '10:00', expected: 0, checked_in: 3, checked_out: 0 },
        ]}
      />,
    );
    expect(container.querySelector('.visitor-activity-chart__svg')).toBeTruthy();
    expect(screen.getByText('Check-ins')).toBeInTheDocument();
    expect(screen.getByText('10:00')).toBeInTheDocument();
  });
});

describe('Dashboard page wiring', () => {
  it('does not use date slice orphan labels', async () => {
    const { readFileSync } = await import('node:fs');
    const { dirname, resolve } = await import('node:path');
    const { fileURLToPath } = await import('node:url');
    const page = readFileSync(
      resolve(dirname(fileURLToPath(import.meta.url)), '../pages/dashboard/DashboardPage.tsx'),
      'utf8',
    );
    expect(page).toContain('VisitorActivityChart');
    expect(page).not.toContain('slice(-2)');
    expect(page).toContain('useOperationalPolling');
  });
});
