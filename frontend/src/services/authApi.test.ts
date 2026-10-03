import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  getStoredToken,
  setStoredToken,
  clearStoredToken,
  getGoogleAuthUrl,
  devLogin,
  fetchCurrentUser,
  fetchAccountDetails,
  updateAccountProfile,
  logoutUser,
} from './authApi';

describe('authApi client tests', () => {
  let store: Record<string, string> = {};

  const mockLocalStorage = {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };

  beforeEach(() => {
    store = {};
    vi.stubGlobal('localStorage', mockLocalStorage);
    vi.stubGlobal('window', { location: { pathname: '/' } });
    vi.restoreAllMocks();
  });

  it('manages token storage in localStorage correctly', () => {
    expect(getStoredToken()).toBeNull();
    setStoredToken('test-token-123');
    expect(getStoredToken()).toBe('test-token-123');
    clearStoredToken();
    expect(getStoredToken()).toBeNull();
  });

  it('fetches Google OAuth URL successfully', async () => {
    const mockResponse = {
      url: 'https://accounts.google.com/o/oauth2/v2/auth?state=xyz',
      state: 'xyz',
    };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    }));

    const result = await getGoogleAuthUrl();
    expect(result.url).toBe(mockResponse.url);
    expect(result.state).toBe(mockResponse.state);
  });

  it('performs dev login, stores token and returns mapped AuthUser', async () => {
    const mockAuthResponse = {
      access_token: 'jwt-access-token-abc',
      token_type: 'bearer',
      expires_in: 3600,
      user: {
        id: 'u-123',
        display_name: 'Saurabh Kumar',
        email: 'saurabh@example.com',
        is_active: true,
        created_at: '2026-08-17T08:00:00Z',
        updated_at: '2026-08-17T08:00:00Z',
      },
    };

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockAuthResponse,
    }));

    const user = await devLogin({ email: 'saurabh@example.com', display_name: 'Saurabh Kumar' });
    expect(user.id).toBe('u-123');
    expect(user.displayName).toBe('Saurabh Kumar');
    expect(user.email).toBe('saurabh@example.com');
    expect(getStoredToken()).toBe('jwt-access-token-abc');
  });

  it('fetches current user with Authorization header', async () => {
    setStoredToken('jwt-sample-token');
    const mockUserResponse = {
      id: 'u-123',
      display_name: 'Saurabh Kumar',
      email: 'saurabh@example.com',
      is_active: true,
      created_at: '2026-08-17T08:00:00Z',
      updated_at: '2026-08-17T08:00:00Z',
    };

    vi.stubGlobal('fetch', vi.fn().mockImplementation((_url, options) => {
      expect(options.headers['Authorization']).toBe('Bearer jwt-sample-token');
      return Promise.resolve({
        ok: true,
        json: async () => mockUserResponse,
      });
    }));

    const user = await fetchCurrentUser();
    expect(user.displayName).toBe('Saurabh Kumar');
  });

  it('fetches account details and maps identities', async () => {
    setStoredToken('jwt-sample-token');
    const mockAccountResponse = {
      user: {
        id: 'u-123',
        display_name: 'Saurabh Kumar',
        email: 'saurabh@example.com',
        is_active: true,
        created_at: '2026-08-17T08:00:00Z',
        updated_at: '2026-08-17T08:00:00Z',
      },
      identities: [
        {
          id: 'ident-1',
          provider: 'google',
          provider_subject: 'google-sub-123',
          provider_email: 'saurabh@example.com',
          created_at: '2026-08-17T08:00:00Z',
          last_login_at: '2026-10-03T10:00:00Z',
        },
      ],
      active_sessions_count: 2,
    };

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockAccountResponse,
    }));

    const details = await fetchAccountDetails();
    expect(details.user.displayName).toBe('Saurabh Kumar');
    expect(details.identities.length).toBe(1);
    expect(details.identities[0].provider).toBe('google');
    expect(details.activeSessionsCount).toBe(2);
  });

  it('updates account profile display name', async () => {
    setStoredToken('jwt-sample-token');
    const mockUpdatedUser = {
      id: 'u-123',
      display_name: 'Updated Name',
      email: 'saurabh@example.com',
      is_active: true,
      created_at: '2026-08-17T08:00:00Z',
      updated_at: '2026-10-03T10:00:00Z',
    };

    vi.stubGlobal('fetch', vi.fn().mockImplementation((_url, options) => {
      expect(options.method).toBe('PATCH');
      expect(JSON.parse(options.body)).toEqual({ display_name: 'Updated Name' });
      return Promise.resolve({
        ok: true,
        json: async () => mockUpdatedUser,
      });
    }));

    const updated = await updateAccountProfile('Updated Name');
    expect(updated.displayName).toBe('Updated Name');
  });

  it('clears stored token upon logout', async () => {
    setStoredToken('jwt-to-clear');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'success' }),
    }));

    await logoutUser();
    expect(getStoredToken()).toBeNull();
  });
});
