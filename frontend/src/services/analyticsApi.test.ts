import { describe, it, expect, beforeEach, vi } from 'vitest';
import { fetchAnalytics } from './analyticsApi';

describe('analyticsApi client tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockAnalyticsRaw = {
    range: '7d',
    start_date: '2026-09-28',
    end_date: '2026-10-04',
    timezone: 'UTC',
    summary: {
      total_study_time_seconds: 7200,
      average_session_duration_seconds: 3600,
      average_focus_score: 85.5,
      total_distracted_seconds: 600,
      total_away_seconds: 200,
      total_distractions: 4,
      completed_sessions_count: 2,
    },
    trend: {
      title: 'Focus Score Trend',
      subtitle: 'Weekly focus score · last 7 days',
      badgeText: 'This week',
      score: '86%',
      changeText: '+5% vs last week',
      days: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
      data: [
        {
          date: '2026-10-04',
          label: 'Sun',
          study_time_seconds: 3600,
          distracted_seconds: 300,
          focus_score: 85.5,
          distraction_count: 2,
          session_count: 1,
        },
      ],
      trendLines: [
        { x1: 40, y1: 50, x2: 180, y2: 45, startPoint: true, endPoint: false },
      ],
      points: [
        { cx: 40, cy: 50, score: 85.5, date: '2026-10-04', day: 'Sun' },
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
          duration_seconds: 300,
          duration: '5m',
          percentWidth: 100,
        },
      ],
      footerSummary: '4 detected events · 10m distracted',
      total_distraction_seconds: 600,
      total_events: 4,
    },
    comparison: {
      title: 'Comparison',
      rows: [
        { id: 'comp-today', period: 'Today', score: '86%', duration: '2h 00m' },
      ],
      dateRange: 'Sep 28 — Oct 04, 2026',
    },
  };

  it('fetches analytics with selected range and browser timezone with credentials: include', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockAnalyticsRaw,
    });
    vi.stubGlobal('fetch', fetchMock);

    const data = await fetchAnalytics('7d', 'UTC');

    expect(data.range).toBe('7d');
    expect(data.summary.totalStudyTimeSeconds).toBe(7200);
    expect(data.summary.averageFocusScore).toBe(85.5);
    expect(data.summary.completedSessionsCount).toBe(2);
    expect(data.trend.score).toBe('86%');
    expect(data.breakdown.categories[0].category).toBe('phone_use');
    expect(data.comparison.rows[0].period).toBe('Today');

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/analytics?range=7d&tz=UTC'),
      expect.objectContaining({
        method: 'GET',
        credentials: 'include',
      })
    );
  });

  it('handles 401 unauthenticated on fetchAnalytics', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
    }));

    await expect(fetchAnalytics('7d')).rejects.toThrow('Not authenticated');
  });
});
