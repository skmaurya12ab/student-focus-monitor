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
} from '../types/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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
