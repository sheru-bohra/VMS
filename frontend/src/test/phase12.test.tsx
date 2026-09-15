import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { DevLoginPage } from '../pages/login/LoginPage';
import { isEntraAuthMode } from '../config/auth';
import { filterNavByPermissions } from '../utils/permissions';

vi.mock('../config/auth', async () => {
  const actual = await vi.importActual('../config/auth');
  return {
    ...actual,
    isEntraAuthMode: vi.fn(() => false),
  };
});

describe('Phase 12 frontend', () => {
  beforeEach(() => {
    vi.mocked(isEntraAuthMode).mockReturnValue(false);
  });

  it('renders dev login page', () => {
    render(
      <BrowserRouter>
        <DevLoginPage />
      </BrowserRouter>,
    );
    expect(screen.getByText('Visitor Management System')).toBeInTheDocument();
    expect(screen.getByText('Development authentication is active.')).toBeInTheDocument();
  });

  it('administration nav points to administration hub', () => {
    const filtered = filterNavByPermissions(['admins.read']);
    const admin = filtered.find((i) => i.id === 'administration');
    expect(admin?.path).toBe('/administration');
  });
});
