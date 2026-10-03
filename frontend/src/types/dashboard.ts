/**
 * Typed interfaces for Student Focus Monitor Dashboard (Phase 3 Figma Frontend)
 */

export type NavigationTab = 'home' | 'analytics' | 'sessions' | 'settings';

export interface RouteItem {
  id: NavigationTab;
  path: string;
  label: string;
  icon: string;
}

// 01 Home / Live Dashboard Types
export interface LiveStats {
  focused: string;
  distracted: string;
  away: string;
}

export interface FocusScoreData {
  score: number;
  changeText: string;
  sparklineSegments: Array<{
    startX: number;
    startY: number;
    endX: number;
    endY: number;
  }>;
}

export interface TimeManagementData {
  studyTime: string;
  totalLabel: string;
  focusedLabel: string;
  focusedValue: string;
  focusedPercent: number;
  distractedLabel: string;
  distractedValue: string;
  distractedPercent: number;
}

export interface ActivityDistribution {
  value: number;
  heightPercent: number;
}

export interface InteractionActivityData {
  distractions: number;
  subtitle: string;
  todayLabel: string;
  bars: ActivityDistribution[];
}

export interface TimelineSegment {
  id: string;
  state: 'focused' | 'distracted' | 'away';
  startMinutes: number; // minutes from 10:00 AM (0 to 180)
  durationMinutes: number;
}

export interface FocusTimelineData {
  startTimeLabel: string;
  endTimeLabel: string;
  timeMarks: string[];
  segments: TimelineSegment[];
  footerNote: string;
}

export interface HomeDashboardData {
  userName: string;
  greetingTitle: string;
  greetingSubtitle: string;
  assistantPrompt: string;
  liveStatus: string;
  liveStats: LiveStats;
  focusScore: FocusScoreData;
  timeManagement: TimeManagementData;
  interactionActivity: InteractionActivityData;
  focusTimeline: FocusTimelineData;
}

// 02 Focus Analytics Types
export interface WeeklyTrendPoint {
  day: string;
  x: number;
  y: number;
}

export interface FocusScoreTrendData {
  title: string;
  subtitle: string;
  badgeText: string;
  score: string;
  changeText: string;
  days: string[];
  trendLines: Array<{
    x1: number;
    y1: number;
    x2: number;
    y2: number;
    startPoint?: boolean;
    endPoint?: boolean;
  }>;
}

export interface DistractionCategoryItem {
  id: string;
  label: string;
  count: number;
  duration: string;
  percentWidth: number;
}

export interface DistractionBreakdownData {
  title: string;
  categories: DistractionCategoryItem[];
  footerSummary: string;
}

export interface ComparisonRow {
  id: string;
  period: string;
  score: string;
  duration: string;
}

export interface ComparisonData {
  title: string;
  rows: ComparisonRow[];
  dateRange: string;
}

export interface AnalyticsPageData {
  title: string;
  subtitle: string;
  trend: FocusScoreTrendData;
  breakdown: DistractionBreakdownData;
  comparison: ComparisonData;
}

// 03 Sessions History Types
export interface SessionRowData {
  id: string;
  date: string;
  duration: string;
  focus: string;
  distractions: number;
  status: 'Completed' | 'In Progress' | 'Interrupted';
}

export interface SelectedSessionData {
  title: string;
  summary: string;
  topCauses: string;
  startTime: string;
  endTime: string;
  segments: TimelineSegment[];
}

export interface SessionsHistoryData {
  title: string;
  subtitle: string;
  searchPlaceholder: string;
  dateFilterLabel: string;
  sessions: SessionRowData[];
  selectedSession: SelectedSessionData;
}

// 04 Settings Types
export interface AlertThresholdItem {
  id: string;
  label: string;
  seconds: number;
  maxSeconds: number;
}

export interface AlertNotificationItem {
  id: string;
  label: string;
  enabled: boolean;
}

export interface WebcamSettingsData {
  deviceLabel: string;
  selectedDevice: string;
  previewQualityLabel: string;
  qualityValue: string;
}

export interface UserProfileData {
  initial: string;
  name: string;
  accountType: string;
}

export interface SettingsData {
  title: string;
  subtitle: string;
  thresholdsTitle: string;
  thresholdsSubtitle: string;
  thresholds: AlertThresholdItem[];
  notificationsTitle: string;
  notifications: AlertNotificationItem[];
  webcamTitle: string;
  webcam: WebcamSettingsData;
  profileTitle: string;
  profile: UserProfileData;
}
