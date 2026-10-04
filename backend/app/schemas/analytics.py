"""Pydantic schemas for Historical Focus Analytics."""
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class AnalyticsSummary(BaseModel):
    """Aggregate summary statistics across completed sessions in the selected window."""
    total_study_time_seconds: float = 0.0
    average_session_duration_seconds: float = 0.0
    average_focus_score: Optional[float] = None
    total_distracted_seconds: float = 0.0
    total_away_seconds: float = 0.0
    total_distractions: int = 0
    completed_sessions_count: int = 0


class DailyTrendItem(BaseModel):
    """Metrics for a single day bucket in user local timezone."""
    date: str  # YYYY-MM-DD
    label: str  # e.g. "Mon" or "10/04"
    study_time_seconds: float = 0.0
    distracted_seconds: float = 0.0
    focus_score: Optional[float] = None  # None if no sessions on this day (not 0%)
    distraction_count: int = 0
    session_count: int = 0


class TrendLineSegment(BaseModel):
    """SVG line segment for visual focus trend graph."""
    x1: float
    y1: float
    x2: float
    y2: float
    startPoint: bool = False
    endPoint: bool = False


class TrendPoint(BaseModel):
    """Point on the trend SVG graph for tooltip/hover."""
    cx: float
    cy: float
    score: float
    date: str
    day: str


class AnalyticsTrend(BaseModel):
    """Focus score trend card representation matching approved Figma design."""
    title: str = "Focus Score Trend"
    subtitle: str = "Weekly focus score · last 7 days"
    badgeText: str = "This week"
    score: str = "—"
    changeText: str = ""
    days: list[str] = []
    data: list[DailyTrendItem] = []
    trendLines: list[TrendLineSegment] = []
    points: list[TrendPoint] = []


class CategoryBreakdownItem(BaseModel):
    """Distraction metrics for a canonical detector category."""
    id: str
    category: str
    label: str
    count: int = 0
    duration_seconds: float = 0.0
    duration: str = "0m"
    percentWidth: float = 0.0


class AnalyticsBreakdown(BaseModel):
    """Distraction category breakdown card representation."""
    title: str = "Distraction Breakdown"
    categories: list[CategoryBreakdownItem] = []
    footerSummary: str = "0 detected events · 0 min distracted"
    total_distraction_seconds: float = 0.0
    total_events: int = 0


class ComparisonRow(BaseModel):
    """Single period comparison row matching Figma comparison card."""
    id: str
    period: str
    score: str
    duration: str


class AnalyticsComparison(BaseModel):
    """Comparison card representation across temporal horizons."""
    title: str = "Comparison"
    rows: list[ComparisonRow] = []
    dateRange: str = ""


class AnalyticsResponse(BaseModel):
    """Comprehensive historical analytics response."""
    range: str = "7d"
    start_date: str
    end_date: str
    timezone: str = "UTC"
    summary: AnalyticsSummary
    trend: AnalyticsTrend
    breakdown: AnalyticsBreakdown
    comparison: AnalyticsComparison
