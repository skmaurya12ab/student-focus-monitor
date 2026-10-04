/**
 * Study Session Lifecycle API client communicating with FastAPI backend.
 * Uses secure HttpOnly cookie session authentication (credentials: 'include').
 */
import {
  StudySession,
  StudySessionCreatePayload,
  StudySessionResponseRaw,
  StudySessionStopResponseRaw,
  ActiveSessionResponse,
  StudySessionDetail,
  SessionHistoryResponse,
  DetectionEventItem,
} from '../types/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function mapEvent(raw: any): DetectionEventItem {
  return {
    id: raw.id,
    sessionId: raw.session_id,
    eventType: raw.event_type,
    startedAt: raw.started_at,
    endedAt: raw.ended_at,
    durationSeconds: raw.duration_seconds,
    detectorVersion: raw.detector_version,
    metadataJson: raw.metadata_json,
    createdAt: raw.created_at,
  };
}

function mapDetail(raw: any): StudySessionDetail {
  const base = mapSession(raw);
  return {
    ...base,
    events: (raw.events || []).map(mapEvent),
    topCauses: raw.top_causes || '',
    categoryBreakdown: (raw.category_breakdown || []).map((c: any) => ({
      category: c.category,
      label: c.label,
      count: c.count,
      durationSeconds: c.duration_seconds,
    })),
  };
}


function mapSession(raw: StudySessionResponseRaw): StudySession {
  return {
    id: raw.id,
    userId: raw.user_id,
    status: raw.status,
    startedAt: raw.started_at,
    endedAt: raw.ended_at,
    totalDurationSeconds: raw.total_duration_seconds,
    focusedSeconds: raw.focused_seconds,
    distractedSeconds: raw.distracted_seconds,
    awaySeconds: raw.away_seconds,
    focusScore: raw.focus_score,
    distractionCount: raw.distraction_count ?? 0,
    detectorVersion: raw.detector_version,
    featureSchemaVersion: raw.feature_schema_version,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

/**
 * Start a new study session for the authenticated user.
 */
export async function startStudySession(
  payload?: StudySessionCreatePayload
): Promise<StudySession> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/sessions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify(payload || {}),
    });

    if (!response.ok) {
      const errJson = await response.json().catch(() => ({}));
      const detail = errJson.detail || response.statusText;
      if (response.status === 401) {
        throw new Error('Not authenticated');
      }
      if (response.status === 409) {
        throw new Error(detail || 'Active session already exists');
      }
      throw new Error(`Failed to start session: ${detail}`);
    }

    const raw: StudySessionResponseRaw = await response.json();
    return mapSession(raw);
  } catch (err: any) {
    if (
      err.name === 'TypeError' ||
      err.message?.includes('Failed to fetch') ||
      err.message?.includes('NetworkError')
    ) {
      throw new Error('BACKEND_UNAVAILABLE');
    }
    throw err;
  }
}

/**
 * Retrieve the currently active study session, or null if none is active.
 */
export async function fetchActiveStudySession(): Promise<StudySession | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/sessions/active`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      credentials: 'include',
    });

    if (!response.ok) {
      if (response.status === 401) {
        return null;
      }
      throw new Error(`Failed to fetch active session: ${response.statusText}`);
    }

    const data: ActiveSessionResponse = await response.json();
    return data.session ? mapSession(data.session) : null;
  } catch (err: any) {
    if (
      err.name === 'TypeError' ||
      err.message?.includes('Failed to fetch') ||
      err.message?.includes('NetworkError')
    ) {
      throw new Error('BACKEND_UNAVAILABLE');
    }
    throw err;
  }
}

/**
 * Retrieve the most recent study session (active or completed), or null if none exists.
 */
export async function fetchLatestStudySession(): Promise<StudySession | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/sessions/latest`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      credentials: 'include',
    });

    if (!response.ok) {
      if (response.status === 401) {
        return null;
      }
      throw new Error(`Failed to fetch latest session: ${response.statusText}`);
    }

    const data: ActiveSessionResponse = await response.json();
    return data.session ? mapSession(data.session) : null;
  } catch (err: any) {
    if (
      err.name === 'TypeError' ||
      err.message?.includes('Failed to fetch') ||
      err.message?.includes('NetworkError')
    ) {
      throw new Error('BACKEND_UNAVAILABLE');
    }
    throw err;
  }
}

/**
 * Retrieve a specific study session by ID, enforcing ownership.
 */
export async function fetchStudySessionById(sessionId: string): Promise<StudySession> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      credentials: 'include',
    });

    if (!response.ok) {
      if (response.status === 401) throw new Error('Not authenticated');
      if (response.status === 404) throw new Error('Session not found');
      throw new Error(`Failed to fetch session: ${response.statusText}`);
    }

    const raw: StudySessionResponseRaw = await response.json();
    return mapSession(raw);
  } catch (err: any) {
    if (
      err.name === 'TypeError' ||
      err.message?.includes('Failed to fetch') ||
      err.message?.includes('NetworkError')
    ) {
      throw new Error('BACKEND_UNAVAILABLE');
    }
    throw err;
  }
}

/**
 * Stop an active study session and compute authoritative duration.
 */
export async function stopStudySession(sessionId: string): Promise<StudySession> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/stop`, {
      method: 'POST',
      headers: { Accept: 'application/json' },
      credentials: 'include',
    });

    if (!response.ok) {
      const errJson = await response.json().catch(() => ({}));
      const detail = errJson.detail || response.statusText;
      if (response.status === 401) throw new Error('Not authenticated');
      if (response.status === 404) throw new Error('Session not found');
      if (response.status === 409) throw new Error(detail || 'Session is not active');
      throw new Error(`Failed to stop session: ${detail}`);
    }

    const data: StudySessionStopResponseRaw = await response.json();
    return mapSession(data.session);
  } catch (err: any) {
    if (
      err.name === 'TypeError' ||
      err.message?.includes('Failed to fetch') ||
      err.message?.includes('NetworkError')
    ) {
      throw new Error('BACKEND_UNAVAILABLE');
    }
    throw err;
  }
}

/**
 * Retrieve paginated study sessions history for the authenticated user.
 */
export async function fetchSessionHistory(
  page: number = 1,
  pageSize: number = 10,
  status?: string
): Promise<SessionHistoryResponse> {
  try {
    let url = `${API_BASE_URL}/api/sessions/history?page=${page}&page_size=${pageSize}`;
    if (status) {
      url += `&status=${encodeURIComponent(status)}`;
    }

    const response = await fetch(url, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      credentials: 'include',
    });

    if (!response.ok) {
      if (response.status === 401) throw new Error('Not authenticated');
      throw new Error(`Failed to fetch session history: ${response.statusText}`);
    }

    const data = await response.json();
    return {
      items: (data.items || []).map(mapSession),
      total: data.total,
      page: data.page,
      pageSize: data.page_size,
      totalPages: data.total_pages,
    };
  } catch (err: any) {
    if (
      err.name === 'TypeError' ||
      err.message?.includes('Failed to fetch') ||
      err.message?.includes('NetworkError')
    ) {
      throw new Error('BACKEND_UNAVAILABLE');
    }
    throw err;
  }
}

/**
 * Retrieve detailed study session by ID including discrete detection events.
 */
export async function fetchSessionDetail(sessionId: string): Promise<StudySessionDetail> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      credentials: 'include',
    });

    if (!response.ok) {
      if (response.status === 401) throw new Error('Not authenticated');
      if (response.status === 404) throw new Error('Session not found');
      throw new Error(`Failed to fetch session detail: ${response.statusText}`);
    }

    const raw = await response.json();
    return mapDetail(raw);
  } catch (err: any) {
    if (
      err.name === 'TypeError' ||
      err.message?.includes('Failed to fetch') ||
      err.message?.includes('NetworkError')
    ) {
      throw new Error('BACKEND_UNAVAILABLE');
    }
    throw err;
  }
}

