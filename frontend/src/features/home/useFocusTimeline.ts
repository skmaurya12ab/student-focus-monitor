/**
 * Dynamic Focus Timeline hook and pure state progression logic (Phase 9).
 * Maintains authoritative state progression segments for the active study session.
 * Does not fabricate data: a newly started session begins with a short/empty timeline.
 */
import { useState, useEffect, useRef, useMemo } from 'react';
import { LiveDetectionResult } from '../../types/liveTransport';

export type TimelineState = 'focused' | 'distracted' | 'away' | 'calibrating';

export interface LiveTimelineSegment {
  id: string;
  state: TimelineState;
  durationSeconds: number;
  startTime: Date;
}

export interface FocusTimelineViewModel {
  segments: LiveTimelineSegment[];
  totalSeconds: number;
  timeMarks: string[];
  startTimeLabel: string;
  endTimeLabel: string;
  isEmpty: boolean;
}

export function formatClockTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

/**
 * Pure function to compute next timeline segments list on new incoming detector state.
 */
export function calculateNextTimelineSegments(
  prevSegments: LiveTimelineSegment[],
  currentState: TimelineState,
  deltaSeconds: number = 1.0,
  maxSegments: number = 100
): LiveTimelineSegment[] {
  const delta = Math.max(0.1, deltaSeconds);

  if (prevSegments.length === 0) {
    return [
      {
        id: `seg-${Date.now()}`,
        state: currentState,
        durationSeconds: Math.round(delta),
        startTime: new Date(),
      },
    ];
  }

  const lastIdx = prevSegments.length - 1;
  const lastSeg = prevSegments[lastIdx];

  // If state is identical, extend the current segment
  if (lastSeg.state === currentState) {
    const updated = [...prevSegments];
    updated[lastIdx] = {
      ...lastSeg,
      durationSeconds: lastSeg.durationSeconds + delta,
    };
    return updated;
  }

  // If state changed, append a new segment
  const newSegment: LiveTimelineSegment = {
    id: `seg-${Date.now()}-${prevSegments.length}`,
    state: currentState,
    durationSeconds: Math.max(1, Math.round(delta)),
    startTime: new Date(),
  };

  if (prevSegments.length >= maxSegments) {
    return [...prevSegments.slice(1), newSegment];
  }
  return [...prevSegments, newSegment];
}

/**
 * Pure function to build view model (durations, dynamic time marks, labels).
 */
export function buildFocusTimelineViewModel(
  segments: LiveTimelineSegment[],
  sessionId: string | null | undefined,
  sessionStartedAt: string | null | undefined
): FocusTimelineViewModel {
  if (!sessionId || segments.length === 0) {
    return {
      segments: [],
      totalSeconds: 0,
      timeMarks: ['Start', 'Now'],
      startTimeLabel: '—',
      endTimeLabel: '—',
      isEmpty: true,
    };
  }

  const totalSeconds = segments.reduce((sum, seg) => sum + seg.durationSeconds, 0);
  const startDate = sessionStartedAt ? new Date(sessionStartedAt) : segments[0].startTime;
  const endDate = new Date(startDate.getTime() + totalSeconds * 1000);

  const startTimeLabel = formatClockTime(startDate);
  const endTimeLabel = formatClockTime(endDate);

  // Build evenly spaced dynamic time marks
  const marks: string[] = [];
  if (totalSeconds < 120) {
    marks.push(startTimeLabel);
    marks.push(endTimeLabel);
  } else {
    const numMarks = 5;
    for (let i = 0; i < numMarks; i++) {
      const markMs = startDate.getTime() + (totalSeconds * 1000 * i) / (numMarks - 1);
      marks.push(formatClockTime(new Date(markMs)));
    }
  }

  return {
    segments,
    totalSeconds,
    timeMarks: marks,
    startTimeLabel,
    endTimeLabel,
    isEmpty: false,
  };
}

export function useFocusTimeline(
  sessionId: string | null | undefined,
  sessionStartedAt: string | null | undefined,
  latestDetection: LiveDetectionResult | null,
  isLive: boolean
): FocusTimelineViewModel {
  const [segments, setSegments] = useState<LiveTimelineSegment[]>(() => {
    if (!sessionId) return [];
    const initialDate = sessionStartedAt ? new Date(sessionStartedAt) : new Date();
    return [
      {
        id: `seg-${Date.now()}-init`,
        state: 'focused',
        durationSeconds: 1,
        startTime: initialDate,
      },
    ];
  });
  const currentSessionIdRef = useRef<string | null>(sessionId || null);
  const lastTimestampRef = useRef<number | null>(null);

  // Reset or initialize when session changes
  useEffect(() => {
    if (!sessionId) {
      setSegments([]);
      currentSessionIdRef.current = null;
      lastTimestampRef.current = null;
      return;
    }

    if (currentSessionIdRef.current !== sessionId) {
      currentSessionIdRef.current = sessionId;
      const initialDate = sessionStartedAt ? new Date(sessionStartedAt) : new Date();
      setSegments([
        {
          id: `seg-${Date.now()}-init`,
          state: 'focused',
          durationSeconds: 1,
          startTime: initialDate,
        },
      ]);
      lastTimestampRef.current = null;
    }
  }, [sessionId, sessionStartedAt]);

  // Append or accumulate segments based on live detector state
  useEffect(() => {
    if (!sessionId || !isLive || !latestDetection) {
      return;
    }

    const rawState = latestDetection.state;
    const currentState: TimelineState =
      rawState === 'distracted'
        ? 'distracted'
        : rawState === 'away'
        ? 'away'
        : rawState === 'calibrating'
        ? 'calibrating'
        : 'focused';

    const currentTimestamp = latestDetection.timestamp || Date.now() / 1000;
    const prevTimestamp = lastTimestampRef.current;
    lastTimestampRef.current = currentTimestamp;

    const delta = prevTimestamp ? Math.min(2.0, Math.max(0.1, currentTimestamp - prevTimestamp)) : 1.0;

    setSegments((prev) => calculateNextTimelineSegments(prev, currentState, delta));
  }, [sessionId, isLive, latestDetection]);

  return useMemo(() => {
    return buildFocusTimelineViewModel(segments, sessionId, sessionStartedAt);
  }, [segments, sessionId, sessionStartedAt]);
}
