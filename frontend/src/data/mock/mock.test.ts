import { describe, it, expect } from 'vitest';
import {
  mockHomeData,
  mockAnalyticsData,
  mockSessionsData,
  mockSettingsData,
} from './index';

describe('Phase 3 Mock Data Contracts', () => {
  describe('Home Dashboard Mock Data', () => {
    it('contains valid user greeting and primary actions', () => {
      expect(mockHomeData.userName).toBe('Saurabh');
      expect(mockHomeData.greetingTitle).toContain('Hi Saurabh');
      expect(mockHomeData.liveStatus).toBe('LIVE');
    });

    it('contains live statistics matching Figma design', () => {
      expect(mockHomeData.liveStats.focused).toBe('01:42:18');
      expect(mockHomeData.liveStats.distracted).toBe('00:18:34');
      expect(mockHomeData.liveStats.away).toBe('00:04:12');
    });

    it('contains valid metric cards data', () => {
      expect(mockHomeData.focusScore.score).toBe(78);
      expect(mockHomeData.timeManagement.studyTime).toBe('3h 24m');
      expect(mockHomeData.timeManagement.focusedPercent).toBe(78);
      expect(mockHomeData.interactionActivity.distractions).toBe(9);
      expect(mockHomeData.interactionActivity.bars.length).toBeGreaterThan(0);
    });

    it('contains timeline segments and time marks from 10:00 AM to 1:00 PM', () => {
      expect(mockHomeData.focusTimeline.startTimeLabel).toBe('10:00 AM');
      expect(mockHomeData.focusTimeline.endTimeLabel).toBe('1:00 PM');
      expect(mockHomeData.focusTimeline.timeMarks).toContain('10:00 AM');
      expect(mockHomeData.focusTimeline.timeMarks).toContain('1:00 PM');
      expect(mockHomeData.focusTimeline.segments.length).toBeGreaterThan(5);
    });
  });

  describe('Analytics Mock Data', () => {
    it('contains weekly trend data matching Figma node 2:814', () => {
      expect(mockAnalyticsData.trend.score).toBe('82%');
      expect(mockAnalyticsData.trend.changeText).toBe('+8% vs last week');
      expect(mockAnalyticsData.trend.days).toEqual([
        'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'
      ]);
    });

    it('contains distraction categories with counts and durations', () => {
      const categories = mockAnalyticsData.breakdown.categories;
      expect(categories.length).toBe(5);
      expect(categories[0].label).toBe('Phone use');
      expect(categories[0].count).toBe(34);
      expect(categories[0].duration).toBe('18m');
      expect(mockAnalyticsData.breakdown.footerSummary).toContain('99 detected events');
    });

    it('contains comparison rows for today, this week, and this month', () => {
      const rows = mockAnalyticsData.comparison.rows;
      expect(rows.length).toBe(3);
      expect(rows[0].period).toBe('Today');
      expect(rows[0].score).toBe('78%');
      expect(mockAnalyticsData.comparison.dateRange).toBe('Aug 17 — Aug 23, 2026');
    });
  });

  describe('Sessions History Mock Data', () => {
    it('contains 5 recorded sessions matching Figma node 2:900', () => {
      expect(mockSessionsData.sessions.length).toBe(5);
      expect(mockSessionsData.sessions[0].date).toBe('Aug 23, 2026');
      expect(mockSessionsData.sessions[0].duration).toBe('3h 24m');
      expect(mockSessionsData.sessions[0].focus).toBe('78%');
      expect(mockSessionsData.sessions[0].status).toBe('Completed');
    });

    it('contains selected session detail structure', () => {
      expect(mockSessionsData.selectedSession.title).toContain('Aug 23, 2026');
      expect(mockSessionsData.selectedSession.topCauses).toContain('Phone use');
      expect(mockSessionsData.selectedSession.startTime).toBe('10:00 AM');
      expect(mockSessionsData.selectedSession.endTime).toBe('1:24 PM');
    });
  });

  describe('Settings Mock Data', () => {
    it('contains alert threshold defaults matching Figma node 2:982', () => {
      const thresholds = mockSettingsData.thresholds;
      expect(thresholds.length).toBe(5);
      expect(thresholds.find((t) => t.label === 'Yawning')?.seconds).toBe(2);
      expect(thresholds.find((t) => t.label === 'Phone use')?.seconds).toBe(6);
      expect(thresholds.find((t) => t.label === 'Bad posture')?.seconds).toBe(8);
      expect(thresholds.find((t) => t.label === 'Sleeping posture')?.seconds).toBe(4);
      expect(thresholds.find((t) => t.label === 'Away from seat')?.seconds).toBe(10);
    });

    it('contains notification toggles and webcam configuration', () => {
      expect(mockSettingsData.notifications.length).toBe(3);
      expect(mockSettingsData.webcam.selectedDevice).toBe('Integrated Camera - 720p');
      expect(mockSettingsData.profile.name).toBe('Saurabh Kumar');
    });
  });
});
