/**
 * Analytics API client for historical focus statistics and performance metrics.
 * Communicates with FastAPI /api/analytics endpoints using HttpOnly session authentication.
 */
import { AnalyticsData } from '../types/analytics';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function getBrowserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

/**
 * Fetch authoritative historical focus analytics for the authenticated user.
 */
export async function fetchAnalytics(
  range: '7d' | '30d' | 'all' = '7d',
  tz?: string
): Promise<AnalyticsData> {
  const resolvedTz = tz || getBrowserTimezone();
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/analytics?range=${range}&tz=${encodeURIComponent(resolvedTz)}`,
      {
        method: 'GET',
        headers: { Accept: 'application/json' },
        credentials: 'include',
      }
    );

    if (!response.ok) {
      if (response.status === 401) throw new Error('Not authenticated');
      throw new Error(`Failed to fetch analytics: ${response.statusText}`);
    }

    const data = await response.json();
    return {
      range: data.range,
      startDate: data.start_date,
      endDate: data.end_date,
      timezone: data.timezone,
      summary: {
        totalStudyTimeSeconds: data.summary.total_study_time_seconds,
        averageSessionDurationSeconds: data.summary.average_session_duration_seconds,
        averageFocusScore: data.summary.average_focus_score,
        totalDistractedSeconds: data.summary.total_distracted_seconds,
        totalAwaySeconds: data.summary.total_away_seconds,
        totalDistractions: data.summary.total_distractions,
        completedSessionsCount: data.summary.completed_sessions_count,
      },
      trend: {
        title: data.trend.title,
        subtitle: data.trend.subtitle,
        badgeText: data.trend.badgeText,
        score: data.trend.score,
        changeText: data.trend.changeText,
        days: data.trend.days || [],
        data: (data.trend.data || []).map((d: any) => ({
          date: d.date,
          label: d.label,
          studyTimeSeconds: d.study_time_seconds,
          distractedSeconds: d.distracted_seconds,
          focusScore: d.focus_score,
          distractionCount: d.distraction_count,
          sessionCount: d.session_count,
        })),
        trendLines: (data.trend.trendLines || []).map((l: any) => ({
          x1: l.x1,
          y1: l.y1,
          x2: l.x2,
          y2: l.y2,
          startPoint: Boolean(l.startPoint),
          endPoint: Boolean(l.endPoint),
        })),
        points: (data.trend.points || []).map((p: any) => ({
          cx: p.cx,
          cy: p.cy,
          score: p.score,
          date: p.date,
          day: p.day,
        })),
      },
      breakdown: {
        title: data.breakdown.title,
        categories: (data.breakdown.categories || []).map((c: any) => ({
          id: c.id,
          category: c.category,
          label: c.label,
          count: c.count,
          durationSeconds: c.duration_seconds,
          duration: c.duration,
          percentWidth: c.percentWidth,
        })),
        footerSummary: data.breakdown.footerSummary,
        totalDistractionSeconds: data.breakdown.total_distraction_seconds,
        totalEvents: data.breakdown.total_events,
      },
      comparison: {
        title: data.comparison.title,
        rows: (data.comparison.rows || []).map((r: any) => ({
          id: r.id,
          period: r.period,
          score: r.score,
          duration: r.duration,
        })),
        dateRange: data.comparison.dateRange,
      },
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
