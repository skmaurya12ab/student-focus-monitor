import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderToString } from 'react-dom/server';
import { SettingsPage } from './SettingsPage';
import { mockSettingsData } from '../../data/mock/settingsMock';
import * as settingsApi from '../../services/settingsApi';

const mockAuthState = {
  isAuthenticated: true,
  user: { id: 'u1', email: 'settings@example.com', displayName: 'Settings Student' },
};

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => mockAuthState,
}));

describe('SettingsPage (Phase 9 Correction Alert Thresholds)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders all canonical threshold rows and notification switches from Figma specification', () => {
    const html = renderToString(
      <SettingsPage data={mockSettingsData} onNavigateToAccount={() => {}} />
    );

    // Verify canonical threshold categories
    expect(html).toContain('Yawning');
    expect(html).toContain('Phone use');
    expect(html).toContain('Bad posture');
    expect(html).toContain('Sleeping posture');
    expect(html).toContain('Away from seat');

    // Verify notification switches
    expect(html).toContain('Beep / sound alerts');
    expect(html).toContain('On-screen banner alerts');
    expect(html).toContain('Session end summary');

    // Verify action button
    expect(html).toContain('Save changes');
    expect(html).toContain('btn-save-changes');
  });

  it('contains slider roles and accessible values for threshold tuning', () => {
    const html = renderToString(
      <SettingsPage data={mockSettingsData} onNavigateToAccount={() => {}} />
    );

    expect(html).toContain('role="slider"');
    expect(html).toContain('aria-label="Adjust threshold for Phone use"');
    expect(html).toContain('role="switch"');
    expect(html).toContain('aria-label="Toggle Beep / sound alerts"');
  });

  it('defines fetchUserSettings and updateUserSettings in settingsApi module', () => {
    expect(typeof settingsApi.fetchUserSettings).toBe('function');
    expect(typeof settingsApi.updateUserSettings).toBe('function');
  });
});
