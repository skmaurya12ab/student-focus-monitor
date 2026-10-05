import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  startStudySession,
  fetchActiveStudySession,
  fetchLatestStudySession,
  fetchStudySessionById,
  stopStudySession,
  fetchSessionHistory,
  fetchSessionDetail,
  submitSessionFeedback,
  fetchSessionFeedbacks,
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

  it('fetchSessionHistory calls /api/sessions/history and returns paginated mapped items', async () => {
    const mockHistoryData = {
      items: [
        {
          id: 's-1',
          user_id: 'u-1',
          status: 'completed',
          started_at: '2026-10-04T10:00:00Z',
          ended_at: '2026-10-04T11:00:00Z',
          total_duration_seconds: 3600,
          focused_seconds: 3000,
          distracted_seconds: 400,
          away_seconds: 200,
          focus_score: 83.33,
          distraction_count: 3,
          detector_version: 'v4',
          feature_schema_version: 'telemetry_v1',
          created_at: '2026-10-04T10:00:00Z',
          updated_at: '2026-10-04T11:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
      total_pages: 1,
    };

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockHistoryData,
    });
    vi.stubGlobal('fetch', fetchMock);

    const history = await fetchSessionHistory(1, 10);
    expect(history.total).toBe(1);
    expect(history.items.length).toBe(1);
    expect(history.items[0].id).toBe('s-1');
    expect(history.items[0].distractionCount).toBe(3);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/sessions/history?page=1&page_size=10'),
      expect.objectContaining({ credentials: 'include' })
    );
  });

  it('fetchSessionDetail calls /api/sessions/:id and maps discrete events and category causes', async () => {
    const mockDetailRaw = {
      id: 's-detail-1',
      user_id: 'u-1',
      status: 'completed',
      started_at: '2026-10-04T10:00:00Z',
      ended_at: '2026-10-04T11:00:00Z',
      total_duration_seconds: 3600,
      focused_seconds: 3200,
      distracted_seconds: 400,
      away_seconds: 0,
      focus_score: 88.89,
      distraction_count: 2,
      detector_version: 'v4',
      feature_schema_version: 'telemetry_v1',
      created_at: '2026-10-04T10:00:00Z',
      updated_at: '2026-10-04T11:00:00Z',
      top_causes: 'Top causes: Phone Use · Looking Away',
      category_breakdown: [
        { category: 'phone_use', label: 'Phone Use', count: 1, duration_seconds: 120 },
      ],
      events: [
        {
          id: 'evt-1',
          session_id: 's-detail-1',
          event_type: 'phone_use',
          started_at: '2026-10-04T10:15:00Z',
          ended_at: '2026-10-04T10:17:00Z',
          duration_seconds: 120,
          detector_version: 'v4',
          metadata_json: null,
          created_at: '2026-10-04T10:15:00Z',
        },
      ],
    };

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockDetailRaw,
    });
    vi.stubGlobal('fetch', fetchMock);

    const detail = await fetchSessionDetail('s-detail-1');
    expect(detail.id).toBe('s-detail-1');
    expect(detail.topCauses).toBe('Top causes: Phone Use · Looking Away');
    expect(detail.events.length).toBe(1);
    expect(detail.events[0].eventType).toBe('phone_use');
    expect(detail.events[0].durationSeconds).toBe(120);
    expect(detail.categoryBreakdown.length).toBe(1);
    expect(detail.categoryBreakdown[0].label).toBe('Phone Use');
  });

  it('submits event feedback with credentials: include and maps response', async () => {
    const mockFeedbackRaw = {
      id: 'fb-uuid-1',
      session_id: 's-fb-1',
      detection_event_id: 'evt-1',
      feedback_type: 'correct_detection',
      category: null,
      note: 'Verified phone checking',
      created_at: '2026-10-04T10:20:00Z',
    };

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockFeedbackRaw,
    });
    vi.stubGlobal('fetch', fetchMock);

    const result = await submitSessionFeedback('s-fb-1', {
      detectionEventId: 'evt-1',
      feedbackType: 'correct_detection',
      note: 'Verified phone checking',
    });

    expect(result.id).toBe('fb-uuid-1');
    expect(result.sessionId).toBe('s-fb-1');
    expect(result.detectionEventId).toBe('evt-1');
    expect(result.feedbackType).toBe('correct_detection');
    expect(result.note).toBe('Verified phone checking');

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/sessions/s-fb-1/feedback'),
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        body: JSON.stringify({
          detection_event_id: 'evt-1',
          feedback_type: 'correct_detection',
          category: null,
          note: 'Verified phone checking',
        }),
      })
    );
  });

  it('submits missed detection feedback with structured category', async () => {
    const mockFeedbackRaw = {
      id: 'fb-uuid-2',
      session_id: 's-fb-1',
      detection_event_id: null,
      feedback_type: 'missed_detection',
      category: 'phone_use',
      note: 'Missed quick message check',
      created_at: '2026-10-04T10:25:00Z',
    };

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockFeedbackRaw,
    });
    vi.stubGlobal('fetch', fetchMock);

    const result = await submitSessionFeedback('s-fb-1', {
      feedbackType: 'missed_detection',
      category: 'phone_use',
      note: 'Missed quick message check',
    });

    expect(result.id).toBe('fb-uuid-2');
    expect(result.feedbackType).toBe('missed_detection');
    expect(result.category).toBe('phone_use');
  });

  it('fetches session feedbacks list', async () => {
    const mockList = [
      {
        id: 'fb-1',
        session_id: 's-1',
        detection_event_id: 'evt-1',
        feedback_type: 'correct_detection',
        category: null,
        note: null,
        created_at: '2026-10-04T10:00:00Z',
      },
    ];

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockList,
    });
    vi.stubGlobal('fetch', fetchMock);

    const feedbacks = await fetchSessionFeedbacks('s-1');
    expect(feedbacks.length).toBe(1);
    expect(feedbacks[0].id).toBe('fb-1');
    expect(feedbacks[0].feedbackType).toBe('correct_detection');
  });
});


