import { describe, it, expect, vi, beforeEach } from 'vitest';
import { checkBackendHealth, API_BASE_URL } from './api';

describe('checkBackendHealth', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('has a default API_BASE_URL', () => {
    expect(API_BASE_URL).toBeDefined();
    expect(typeof API_BASE_URL).toBe('string');
  });

  it('returns true when backend returns status: "ok"', async () => {
    const mockResponse = {
      ok: true,
      json: async () => ({ status: 'ok' }),
    };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockResponse));

    const isHealthy = await checkBackendHealth();
    expect(isHealthy).toBe(true);
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/health`,
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('returns false when backend returns non-ok HTTP status', async () => {
    const mockResponse = {
      ok: false,
      status: 500,
      json: async () => ({}),
    };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockResponse));

    const isHealthy = await checkBackendHealth();
    expect(isHealthy).toBe(false);
  });

  it('returns false when backend returns unexpected payload', async () => {
    const mockResponse = {
      ok: true,
      json: async () => ({ status: 'error' }),
    };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockResponse));

    const isHealthy = await checkBackendHealth();
    expect(isHealthy).toBe(false);
  });

  it('returns false when network request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')));

    const isHealthy = await checkBackendHealth();
    expect(isHealthy).toBe(false);
  });
});
