import { describe, it, expect } from 'vitest';
import {
  calculateNextTimelineSegments,
  buildFocusTimelineViewModel,
  LiveTimelineSegment,
} from './useFocusTimeline';

describe('useFocusTimeline pure calculations (Phase 9 Timeline Progression)', () => {
  it('initializes empty segments array on first call', () => {
    const next = calculateNextTimelineSegments([], 'focused', 1.0);
    expect(next).toHaveLength(1);
    expect(next[0].state).toBe('focused');
    expect(next[0].durationSeconds).toBe(1.0);
  });

  it('extends existing segment duration when state remains identical', () => {
    const initial: LiveTimelineSegment[] = [
      { id: 'seg-1', state: 'focused', durationSeconds: 5, startTime: new Date() },
    ];
    const next = calculateNextTimelineSegments(initial, 'focused', 2.0);
    expect(next).toHaveLength(1);
    expect(next[0].state).toBe('focused');
    expect(next[0].durationSeconds).toBe(7.0);
  });

  it('appends new segment when state transitions from focused to distracted', () => {
    const initial: LiveTimelineSegment[] = [
      { id: 'seg-1', state: 'focused', durationSeconds: 30, startTime: new Date() },
    ];
    const next = calculateNextTimelineSegments(initial, 'distracted', 3.0);
    expect(next).toHaveLength(2);
    expect(next[0].state).toBe('focused');
    expect(next[0].durationSeconds).toBe(30);
    expect(next[1].state).toBe('distracted');
    expect(next[1].durationSeconds).toBe(3);
  });

  it('caps total segments at maxSegments to prevent memory leak', () => {
    let segs: LiveTimelineSegment[] = [];
    for (let i = 0; i < 20; i++) {
      const state = i % 2 === 0 ? 'focused' : 'distracted';
      segs = calculateNextTimelineSegments(segs, state, 1.0, 5);
    }
    expect(segs.length).toBeLessThanOrEqual(5);
  });

  describe('buildFocusTimelineViewModel', () => {
    it('returns empty placeholder view model when sessionId is missing or segments empty', () => {
      const vm1 = buildFocusTimelineViewModel([], null, null);
      expect(vm1.isEmpty).toBe(true);
      expect(vm1.segments).toHaveLength(0);
      expect(vm1.startTimeLabel).toBe('—');

      const vm2 = buildFocusTimelineViewModel([], 'test-session', null);
      expect(vm2.isEmpty).toBe(true);
      expect(vm2.segments).toHaveLength(0);
    });

    it('builds real view model with accurate durations and time marks for active session', () => {
      const now = new Date('2026-10-04T10:00:00Z');
      const segments: LiveTimelineSegment[] = [
        { id: 'seg-1', state: 'focused', durationSeconds: 60, startTime: now },
        { id: 'seg-2', state: 'distracted', durationSeconds: 30, startTime: new Date(now.getTime() + 60000) },
        { id: 'seg-3', state: 'focused', durationSeconds: 120, startTime: new Date(now.getTime() + 90000) },
      ];

      const vm = buildFocusTimelineViewModel(segments, 'session-123', now.toISOString());
      expect(vm.isEmpty).toBe(false);
      expect(vm.totalSeconds).toBe(210);
      expect(vm.segments).toHaveLength(3);
      expect(vm.timeMarks.length).toBeGreaterThanOrEqual(2);
      expect(vm.startTimeLabel).toBeDefined();
      expect(vm.endTimeLabel).toBeDefined();
    });
  });
});
