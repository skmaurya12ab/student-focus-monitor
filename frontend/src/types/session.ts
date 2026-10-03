/**
 * TypeScript interfaces for Study Session Lifecycle.
 */
export type SessionStatus = 'active' | 'completed' | 'cancelled';

export interface StudySession {
  id: string;
  userId: string;
  status: SessionStatus;
  startedAt: string;
  endedAt: string | null;
  totalDurationSeconds: number;
  focusedSeconds: number;
  distractedSeconds: number;
  awaySeconds: number;
  focusScore: number | null;
  detectorVersion: string;
  featureSchemaVersion: string;
  createdAt: string;
  updatedAt: string;
}

export interface StudySessionCreatePayload {
  notes?: string;
  device_hint?: string;
}

export interface ActiveSessionResponse {
  session: StudySessionResponseRaw | null;
}

export interface StudySessionResponseRaw {
  id: string;
  user_id: string;
  status: SessionStatus;
  started_at: string;
  ended_at: string | null;
  total_duration_seconds: number;
  focused_seconds: number;
  distracted_seconds: number;
  away_seconds: number;
  focus_score: number | null;
  detector_version: string;
  feature_schema_version: string;
  created_at: string;
  updated_at: string;
}

export interface StudySessionStopResponseRaw {
  status: string;
  session: StudySessionResponseRaw;
}
