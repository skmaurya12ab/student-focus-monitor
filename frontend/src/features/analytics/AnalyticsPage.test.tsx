import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderToString } from 'react-dom/server';
import { AnalyticsPage } from './AnalyticsPage';
import { AnalyticsData } from '../../types/analytics';

describe('AnalyticsPage component tests (Phase 10 Focus Analytics)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockAnalyticsData: AnalyticsData = {
    range: '7d',
    startDate: '2026-09-28',
    endDate: '2026-10-04',
    timezone: 'UTC',
    summary: {
      totalStudyTimeSeconds: 7200,
      averageSessionDurationSeconds: 3600,
      averageFocusScore: 88.0,
      totalDistractedSeconds: 600,
      totalAwaySeconds: 200,
      totalDistractions: 5,
      completedSessionsCount: 2,
    },
    trend: {
      title: 'Focus Score Trend',
      subtitle: 'Weekly focus score · last 7 days',
      badgeText: 'This week',
      score: '88%',
      changeText: '+6% vs last week',
      days: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
      data: [
        {
          date: '2026-10-04',
          label: 'Sun',
          studyTimeSeconds: 3600,
          distractedSeconds: 300,
          focusScore: 88.0,
          distractionCount: 2,
          sessionCount: 1,
        },
      ],
      trendLines: [
        { x1: 40, y1: 50, x2: 180, y2: 42, startPoint: true, endPoint: false },
      ],
      points: [
        { cx: 40, cy: 50, score: 88.0, date: '2026-10-04', day: 'Sun' },
      ],
    },
    breakdown: {
      title: 'Distraction Breakdown',
      categories: [
        {
          id: 'phone_use',
          category: 'phone_use',
          label: 'Phone use',
          count: 3,
          durationSeconds: 360,
          duration: '6m',
          percentWidth: 100,
        },
        {
          id: 'looking_away',
          category: 'looking_away',
          label: 'Looking away',
          count: 2,
          durationSeconds: 240,
          duration: '4m',
          percentWidth: 66.7,
        },
      ],
      footerSummary: '5 detected events · 10m distracted',
      totalDistractionSeconds: 600,
      totalEvents: 5,
    },
    comparison: {
      title: 'Comparison',
      rows: [
        { id: 'comp-today', period: 'Today', score: '88%', duration: '2h 00m' },
        { id: 'comp-week', period: 'This week', score: '88%', duration: '2h 00m' },
      ],
      dateRange: 'Sep 28 — Oct 04, 2026',
    },
  };

  const mockEmptyAnalytics: AnalyticsData = {
    range: '7d',
    startDate: '2026-09-28',
    endDate: '2026-10-04',
    timezone: 'UTC',
    summary: {
      totalStudyTimeSeconds: 0,
      averageSessionDurationSeconds: 0,
      averageFocusScore: null,
      totalDistractedSeconds: 0,
      totalAwaySeconds: 0,
      totalDistractions: 0,
      completedSessionsCount: 0,
    },
    trend: {
      title: 'Focus Score Trend',
      subtitle: 'Weekly focus score · last 7 days',
      badgeText: 'This week',
      score: '—',
      changeText: '',
      days: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
      data: [],
      trendLines: [],
      points: [],
    },
    breakdown: {
      title: 'Distraction Breakdown',
      categories: [],
      footerSummary: '0 detected events · 0m distracted',
      totalDistractionSeconds: 0,
      totalEvents: 0,
    },
    comparison: {
      title: 'Comparison',
      rows: [],
      dateRange: 'Sep 28 — Oct 04, 2026',
    },
  };

  it('renders loading state when initialData is undefined', () => {
    const rawHtml = renderToString(<AnalyticsPage />);
    const html = rawHtml.replace(/<!--.*?-->/g, '');
    expect(html).toContain('Loading analytics...');
    expect(html).toContain('Aggregating historical performance metrics.');
  });

  it('renders empty state when user has 0 completed sessions, without mock numbers', () => {
    const rawHtml = renderToString(<AnalyticsPage initialData={mockEmptyAnalytics} />);
    const html = rawHtml.replace(/<!--.*?-->/g, '');
    expect(html).toContain('No analytics available yet.');
    expect(html).toContain('Complete study sessions to generate focus trends, distraction breakdowns, and historical insights.');

    // Ensure Phase 3 mock numbers are NOT present
    expect(html).not.toContain('01:42:18');
    expect(html).not.toContain('00:18:34');
    expect(html).not.toContain('00:04:12');
    expect(html).not.toContain('3h 24m');
    expect(html).not.toContain('78%');
  });

  it('renders real analytics metrics, breakdown, and comparison from API data', () => {
    const rawHtml = renderToString(<AnalyticsPage initialData={mockAnalyticsData} />);
    const html = rawHtml.replace(/<!--.*?-->/g, '');

    // Titles & Range Selector
    expect(html).toContain('Focus Score Trend');
    expect(html).toContain('7 Days');
    expect(html).toContain('30 Days');
    expect(html).toContain('All Time');

    // Score & change
    expect(html).toContain('88%');
    expect(html).toContain('+6% vs last week');

    // Breakdown
    expect(html).toContain('Distraction Breakdown');
    expect(html).toContain('Phone use');
    expect(html).toContain('6m');
    expect(html).toContain('Looking away');
    expect(html).toContain('4m');
    expect(html).toContain('5 detected events · 10m distracted');

    // Comparison
    expect(html).toContain('Comparison');
    expect(html).toContain('Today');
    expect(html).toContain('2h 00m');
    expect(html).toContain('Sep 28 — Oct 04, 2026');
  });
});

