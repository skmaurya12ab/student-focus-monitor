import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  startStudySession,
  fetchActiveStudySession,
  fetchLatestStudySession,
  fetchStudySessionById,
  stopStudySession,
} from './sessionApi';

describe('sessionApi client tests (HttpOnly cookie session architecture)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockRawSession = {
    id: 'f47ac10b-58cc-4372-a567-0e02b2c3d479',
    user_id: 'u-123',
    status: 'active',
    started_at: '2026-10-03T14:00:00Z',
    ended_at: null,
    total_duration_seconds: null,
    focused_seconds: null,
    distracted_seconds: null,
    away_seconds: null,
    focus_score: null,
    detector_version: '2.0.0',
    feature_schema_version: '1.0.0',
    created_at: '2026-10-03T14:00:00Z',
    updated_at: '2026-10-03T14:00:00Z',
  };

  it('starts a study session with credentials: include and maps fields properly', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockRawSession,
    });
    vi.stubGlobal('fetch', fetchMock);

    const session = await startStudySession();

    expect(session.id).toBe('f47ac10b-58cc-4372-a567-0e02b2c3d479');
    expect(session.userId).toBe('u-123');
    expect(session.status).toBe('active');
    expect(session.startedAt).toBe('2026-10-03T14:00:00Z');
    expect(session.endedAt).toBeNull();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/sessions'),
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
      })
    );
  });

  it('handles 401 Not Authenticated on startStudySession', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
      json: async () => ({ detail: 'Authentication required' }),
    }));

    await expect(startStudySession()).rejects.toThrow('Not authenticated');
  });

  it('handles 409 Conflict on startStudySession when active session exists', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      statusText: 'Conflict',
      json: async () => ({ detail: 'Active study session already exists' }),
    }));

    await expect(startStudySession()).rejects.toThrow('Active study session already exists');
  });

  it('maps network errors to BACKEND_UNAVAILABLE on startStudySession', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));

    await expect(startStudySession()).rejects.toThrow('BACKEND_UNAVAILABLE');
  });

  it('fetches active session when one is present', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ session: mockRawSession }),
    }));

    const session = await fetchActiveStudySession();
    expect(session).not.toBeNull();
    expect(session?.id).toBe(mockRawSession.id);
    expect(session?.status).toBe('active');
  });

  it('returns null when no active session exists', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ session: null }),
    }));

    const session = await fetchActiveStudySession();
    expect(session).toBeNull();
  });

  it('returns null on 401 when fetching active session', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
    }));

    const session = await fetchActiveStudySession();
    expect(session).toBeNull();
  });

  it('fetches session by ID with ownership check', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockRawSession,
    }));

    const session = await fetchStudySessionById('f47ac10b-58cc-4372-a567-0e02b2c3d479');
    expect(session.id).toBe('f47ac10b-58cc-4372-a567-0e02b2c3d479');
  });

  it('handles 404 Not Found on fetchStudySessionById', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: async () => ({ detail: 'Session not found' }),
    }));

    await expect(fetchStudySessionById('nonexistent')).rejects.toThrow('Session not found');
  });

  it('stops study session and returns completed session with duration', async () => {
    const mockCompleted = {
      message: 'Study session completed successfully',
      session: {
        ...mockRawSession,
        status: 'completed',
        ended_at: '2026-10-03T14:45:00Z',
        total_duration_seconds: 2700,
      },
    };

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockCompleted,
    });
    vi.stubGlobal('fetch', fetchMock);

    const session = await stopStudySession('f47ac10b-58cc-4372-a567-0e02b2c3d479');
    expect(session.status).toBe('completed');
    expect(session.endedAt).toBe('2026-10-03T14:45:00Z');
    expect(session.totalDurationSeconds).toBe(2700);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/sessions/f47ac10b-58cc-4372-a567-0e02b2c3d479/stop'),
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
      })
    );
  });

  it('handles 409 Conflict when stopping an already completed session', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      statusText: 'Conflict',
      json: async () => ({ detail: 'Session is not active (status: completed)' }),
    }));

    await expect(stopStudySession('f47ac10b-58cc-4372-a567-0e02b2c3d479')).rejects.toThrow(
      'Session is not active (status: completed)'
    );
  });

  it('fetches latest study session and maps distractionCount correctly', async () => {
    const mockLatestRaw = {
      ...mockRawSession,
      id: '7b4b34fa-7e37-46b7-ae05-eaed010972db',
      status: 'completed',
      total_duration_seconds: 284.98,
      focused_seconds: 235.34,
      distracted_seconds: 13.68,
      away_seconds: 0.0,
      focus_score: '94.51',
      distraction_count: 5,
    };

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ session: mockLatestRaw }),
    }));

    const session = await fetchLatestStudySession();
    expect(session).not.toBeNull();
    expect(session?.id).toBe('7b4b34fa-7e37-46b7-ae05-eaed010972db');
    expect(session?.status).toBe('completed');
    expect(session?.totalDurationSeconds).toBe(284.98);
    expect(session?.focusedSeconds).toBe(235.34);
    expect(session?.distractedSeconds).toBe(13.68);
    expect(session?.awaySeconds).toBe(0.0);
    expect(session?.focusScore).toBe('94.51');
    expect(session?.distractionCount).toBe(5);
  });

  it('returns null when no latest study session exists', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ session: null }),
    }));

    const session = await fetchLatestStudySession();
    expect(session).toBeNull();
  });
});

