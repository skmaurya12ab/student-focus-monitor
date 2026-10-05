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
  distractionCount: number;
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
  distraction_count?: number;
  detector_version: string;
  feature_schema_version: string;
  created_at: string;
  updated_at: string;
}

export interface StudySessionStopResponseRaw {
  status: string;
  session: StudySessionResponseRaw;
}

export type FeedbackType =
  | 'correct_detection'
  | 'false_positive'
  | 'missed_detection'
  | 'other';

export interface SessionFeedback {
  id: string;
  sessionId: string;
  detectionEventId: string | null;
  feedbackType: FeedbackType;
  category: string | null;
  note: string | null;
  createdAt: string;
}

export interface SessionFeedbackCreatePayload {
  detectionEventId?: string | null;
  detection_event_id?: string | null;
  feedbackType?: FeedbackType;
  feedback_type?: FeedbackType;
  category?: string | null;
  note?: string | null;
}

export interface DetectionEventItem {
  id: string;
  sessionId: string;
  eventType: string;
  startedAt: string;
  endedAt: string | null;
  durationSeconds: number | null;
  detectorVersion: string;
  metadataJson: Record<string, any> | null;
  createdAt: string;
  feedback?: SessionFeedback | null;
}

export interface SessionCategorySummaryItem {
  category: string;
  label: string;
  count: number;
  durationSeconds: number;
}

export interface StudySessionDetail extends StudySession {
  events: DetectionEventItem[];
  feedbacks?: SessionFeedback[];
  topCauses: string;
  categoryBreakdown: SessionCategorySummaryItem[];
}

export interface SessionHistoryResponse {
  items: StudySession[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

