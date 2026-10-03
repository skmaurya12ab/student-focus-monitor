import { AnalyticsPageData } from '../../types/dashboard';

export const mockAnalyticsData: AnalyticsPageData = {
  title: 'Focus Analytics',
  subtitle: 'Understand your attention patterns over time.',
  trend: {
    title: 'Focus Score Trend',
    subtitle: 'Weekly focus score · last 7 days',
    badgeText: 'This week',
    score: '82%',
    changeText: '+8% vs last week',
    days: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    trendLines: [
      { x1: 40, y1: 85, x2: 180, y2: 108, startPoint: true, endPoint: false },
      { x1: 180, y1: 58, x2: 320, y2: 48, startPoint: true, endPoint: false },
      { x1: 320, y1: 72, x2: 460, y2: 88, startPoint: true, endPoint: false },
      { x1: 460, y1: 52, x2: 600, y2: 62, startPoint: true, endPoint: false },
      { x1: 600, y1: 38, x2: 740, y2: 32, startPoint: true, endPoint: false },
      { x1: 740, y1: 50, x2: 880, y2: 58, startPoint: true, endPoint: true },
    ],
  },
  breakdown: {
    title: 'Distraction Breakdown',
    categories: [
      { id: 'cat-1', label: 'Phone use', count: 34, duration: '18m', percentWidth: 86 },
      { id: 'cat-2', label: 'Yawning', count: 21, duration: '11m', percentWidth: 53 },
      { id: 'cat-3', label: 'Bad posture', count: 17, duration: '9m', percentWidth: 43 },
      { id: 'cat-4', label: 'Sleeping posture', count: 12, duration: '6m', percentWidth: 30 },
      { id: 'cat-5', label: 'Away from seat', count: 9, duration: '5m', percentWidth: 23 },
    ],
    footerSummary: '99 detected events · 49 min distracted',
  },
  comparison: {
    title: 'Comparison',
    rows: [
      { id: 'comp-1', period: 'Today', score: '78%', duration: '3h 24m' },
      { id: 'comp-2', period: 'This week', score: '82%', duration: '18h 40m' },
      { id: 'comp-3', period: 'This month', score: '76%', duration: '71h 12m' },
    ],
    dateRange: 'Aug 17 — Aug 23, 2026',
  },
};
