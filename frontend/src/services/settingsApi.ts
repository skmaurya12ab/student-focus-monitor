/**
 * User Settings API client communicating with FastAPI backend.
 * Uses secure HttpOnly cookie session authentication (credentials: 'include').
 */
import { UserSettings, UserSettingsUpdatePayload } from '../types/settings';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Fetch authenticated user settings and alert persistence delays.
 */
export async function fetchUserSettings(): Promise<UserSettings> {
  const response = await fetch(`${API_BASE_URL}/api/settings`, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
    credentials: 'include',
  });

  if (!response.ok) {
    const errJson = await response.json().catch(() => ({}));
    const detail = errJson.detail || response.statusText;
    if (response.status === 401) {
      throw new Error('Not authenticated');
    }
    throw new Error(detail || `Failed to fetch settings (${response.status})`);
  }

  return response.json();
}

/**
 * Update authenticated user settings and alert persistence delays.
 */
export async function updateUserSettings(
  payload: UserSettingsUpdatePayload
): Promise<UserSettings> {
  const response = await fetch(`${API_BASE_URL}/api/settings`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errJson = await response.json().catch(() => ({}));
    const detail = errJson.detail || response.statusText;
    if (response.status === 401) {
      throw new Error('Not authenticated');
    }
    throw new Error(detail || `Failed to update settings (${response.status})`);
  }

  return response.json();
}
