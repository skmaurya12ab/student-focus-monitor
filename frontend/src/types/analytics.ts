/**
 * TypeScript interfaces for Focus Analytics.
 */

export interface AnalyticsSummary {
  totalStudyTimeSeconds: number;
  averageSessionDurationSeconds: number;
  averageFocusScore: number | null;
  totalDistractedSeconds: number;
  totalAwaySeconds: number;
  totalDistractions: number;
  completedSessionsCount: number;
}

export interface DailyTrendItem {
  date: string;
  label: string;
  studyTimeSeconds: number;
  distractedSeconds: number;
  focusScore: number | null;
  distractionCount: number;
  sessionCount: number;
}

export interface TrendLineSegment {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  startPoint: boolean;
  endPoint: boolean;
}

export interface TrendPoint {
  cx: number;
  cy: number;
  score: number;
  date: string;
  day: string;
}

export interface AnalyticsTrend {
  title: string;
  subtitle: string;
  badgeText: string;
  score: string;
  changeText: string;
  days: string[];
  data: DailyTrendItem[];
  trendLines: TrendLineSegment[];
  points: TrendPoint[];
}

export interface CategoryBreakdownItem {
  id: string;
  category: string;
  label: string;
  count: number;
  durationSeconds: number;
  duration: string;
  percentWidth: number;
}

export interface AnalyticsBreakdown {
  title: string;
  categories: CategoryBreakdownItem[];
  footerSummary: string;
  totalDistractionSeconds: number;
  totalEvents: number;
}

export interface ComparisonRow {
  id: string;
  period: string;
  score: string;
  duration: string;
}

export interface AnalyticsComparison {
  title: string;
  rows: ComparisonRow[];
  dateRange: string;
}

export interface AnalyticsData {
  range: string;
  startDate: string;
  endDate: string;
  timezone: string;
  summary: AnalyticsSummary;
  trend: AnalyticsTrend;
  breakdown: AnalyticsBreakdown;
  comparison: AnalyticsComparison;
}
