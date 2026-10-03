import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  getGoogleAuthUrl,
  devLogin,
  loginWithGoogle,
  fetchCurrentUser,
  fetchAccountDetails,
  updateAccountProfile,
  logoutUser,
} from './authApi';

describe('authApi client tests (HttpOnly cookie session architecture)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
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

  it('performs dev login with credentials: include and returns mapped AuthUser without exposing tokens', async () => {
    const mockAuthResponse = {
      status: 'success',
      user: {
        id: 'u-123',
        display_name: 'Saurabh Kumar',
        email: 'saurabh@example.com',
        is_active: true,
        created_at: '2026-08-17T08:00:00Z',
        updated_at: '2026-08-17T08:00:00Z',
      },
    };

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockAuthResponse,
    });
    vi.stubGlobal('fetch', fetchMock);

    const user = await devLogin({ email: 'saurabh@example.com', display_name: 'Saurabh Kumar' });
    expect(user.id).toBe('u-123');
    expect(user.displayName).toBe('Saurabh Kumar');
    expect(user.email).toBe('saurabh@example.com');

    // Verify credentials: 'include' was used for cookie transport
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/auth/dev-login'),
      expect.objectContaining({
        credentials: 'include',
        method: 'POST',
      }),
    );
  });

  it('performs loginWithGoogle with credentials: include and returns mapped AuthUser', async () => {
    const mockAuthResponse = {
      status: 'success',
      user: {
        id: 'u-456',
        display_name: 'Emma Watson',
        email: 'emma@example.com',
        is_active: true,
        created_at: '2026-08-17T08:00:00Z',
        updated_at: '2026-08-17T08:00:00Z',
      },
    };

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockAuthResponse,
    });
    vi.stubGlobal('fetch', fetchMock);

    const user = await loginWithGoogle({ id_token: 'mock-id-token' });
    expect(user.displayName).toBe('Emma Watson');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/auth/google'),
      expect.objectContaining({
        credentials: 'include',
        method: 'POST',
      }),
    );
  });

  it('fetches current user via HttpOnly session cookie (/api/auth/me)', async () => {
    const mockUserResponse = {
      id: 'u-123',
      display_name: 'Saurabh Kumar',
      email: 'saurabh@example.com',
      is_active: true,
      created_at: '2026-08-17T08:00:00Z',
      updated_at: '2026-08-17T08:00:00Z',
    };

    const fetchMock = vi.fn().mockImplementation((_url, options) => {
      expect(options.credentials).toBe('include');
      return Promise.resolve({
        ok: true,
        json: async () => mockUserResponse,
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const user = await fetchCurrentUser();
    expect(user.displayName).toBe('Saurabh Kumar');
  });

  it('fetches account details and maps identities without providerSubject', async () => {
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
    expect((details.identities[0] as any).providerSubject).toBeUndefined();
    expect(details.activeSessionsCount).toBe(2);
  });

  it('updates account profile display name with credentials: include', async () => {
    const mockUpdatedUser = {
      id: 'u-123',
      display_name: 'Updated Name',
      email: 'saurabh@example.com',
      is_active: true,
      created_at: '2026-08-17T08:00:00Z',
      updated_at: '2026-10-03T10:00:00Z',
    };

    const fetchMock = vi.fn().mockImplementation((_url, options) => {
      expect(options.method).toBe('PATCH');
      expect(options.credentials).toBe('include');
      expect(JSON.parse(options.body)).toEqual({ display_name: 'Updated Name' });
      return Promise.resolve({
        ok: true,
        json: async () => mockUpdatedUser,
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const updated = await updateAccountProfile('Updated Name');
    expect(updated.displayName).toBe('Updated Name');
  });

  it('calls /api/auth/logout with credentials: include to clear session cookie', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'success' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await logoutUser();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/auth/logout'),
      expect.objectContaining({
        credentials: 'include',
        method: 'POST',
      }),
    );
  });
});

