/**
 * API client for Google authentication and Account management.
 */
import { API_BASE_URL } from './api';
import {
  AccountDetails,
  AuthTokenResponse,
  AuthUser,
  GoogleAuthUrlResponse,
} from '../types/auth';

const TOKEN_STORAGE_KEY = 'sfm_access_token';

export function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function clearStoredToken(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

function getAuthHeaders(): HeadersInit {
  const token = getStoredToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

function mapUserResponse(raw: any): AuthUser {
  return {
    id: raw.id,
    displayName: raw.display_name,
    email: raw.email,
    isActive: raw.is_active,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

/**
 * Retrieve Google OAuth 2.0 authorization URL from backend.
 */
export async function getGoogleAuthUrl(): Promise<GoogleAuthUrlResponse> {
  const response = await fetch(`${API_BASE_URL}/api/auth/google/url`, {
    method: 'GET',
    headers: { Accept: 'application/json' },
  });

  if (!response.ok) {
    throw new Error(`Failed to retrieve Google Auth URL: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Authenticate with Google ID token or authorization code.
 */
export async function loginWithGoogle(payload: {
  id_token?: string;
  code?: string;
  state?: string;
}): Promise<AuthUser> {
  const response = await fetch(`${API_BASE_URL}/api/auth/google`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Google authentication failed');
  }

  const data: AuthTokenResponse = await response.json();
  setStoredToken(data.access_token);
  return mapUserResponse(data.user);
}

/**
 * Development simulated login for testing without live Google credentials.
 */
export async function devLogin(payload?: {
  email?: string;
  display_name?: string;
  google_sub?: string;
}): Promise<AuthUser> {
  const response = await fetch(`${API_BASE_URL}/api/auth/dev-login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(payload || {}),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Development login failed');
  }

  const data: AuthTokenResponse = await response.json();
  setStoredToken(data.access_token);
  return mapUserResponse(data.user);
}

/**
 * Fetch the currently authenticated user profile (/api/auth/me).
 */
export async function fetchCurrentUser(): Promise<AuthUser> {
  const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
    method: 'GET',
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    if (response.status === 401) {
      clearStoredToken();
    }
    throw new Error('Not authenticated');
  }

  const raw = await response.json();
  return mapUserResponse(raw);
}

/**
 * Fetch detailed account information including identities and session counts (/api/account).
 */
export async function fetchAccountDetails(): Promise<AccountDetails> {
  const response = await fetch(`${API_BASE_URL}/api/account`, {
    method: 'GET',
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Failed to load account details: ${response.statusText}`);
  }

  const raw = await response.json();
  return {
    user: mapUserResponse(raw.user),
    identities: (raw.identities || []).map((id: any) => ({
      id: id.id,
      provider: id.provider,
      providerSubject: id.provider_subject,
      providerEmail: id.provider_email,
      createdAt: id.created_at,
      lastLoginAt: id.last_login_at,
    })),
    activeSessionsCount: raw.active_sessions_count || 0,
  };
}

/**
 * Update editable profile fields (such as display name).
 */
export async function updateAccountProfile(displayName: string): Promise<AuthUser> {
  const response = await fetch(`${API_BASE_URL}/api/account`, {
    method: 'PATCH',
    headers: getAuthHeaders(),
    body: JSON.stringify({ display_name: displayName }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to update profile');
  }

  const raw = await response.json();
  return mapUserResponse(raw);
}

/**
 * Terminate the user session and clear credentials.
 */
export async function logoutUser(): Promise<void> {
  const token = getStoredToken();
  if (token) {
    try {
      await fetch(`${API_BASE_URL}/api/auth/logout`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
    } catch {
      // Best-effort backend notification
    }
  }
  clearStoredToken();
}
