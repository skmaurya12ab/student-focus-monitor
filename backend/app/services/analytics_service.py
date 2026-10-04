"""Analytics Service providing historical focus analysis backed by PostgreSQL."""
from datetime import datetime, date, time, timedelta, timezone
from typing import Optional, Any
import uuid
import zoneinfo

from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.study_session import StudySession
from app.db.models.detection_event import DetectionEvent
from app.schemas.analytics import (
    AnalyticsResponse,
    AnalyticsSummary,
    AnalyticsTrend,
    AnalyticsBreakdown,
    AnalyticsComparison,
    DailyTrendItem,
    TrendLineSegment,
    TrendPoint,
    CategoryBreakdownItem,
    ComparisonRow,
)

CANONICAL_CATEGORIES = [
    ("phone_use", "Phone use"),
    ("yawning", "Yawning"),
    ("leaning_back", "Bad posture"),
    ("drowsy", "Sleeping posture"),
    ("away_from_desk", "Away from seat"),
    ("looking_away", "Looking away"),
]


def format_duration_short(seconds: float) -> str:
    """Format duration in seconds to clean readable string (e.g. '3h 24m', '18m', '45s')."""
    total_sec = max(0, int(round(seconds)))
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    secs = total_sec % 60

    if hours > 0:
        return f"{hours}h {minutes}m"
    if minutes > 0:
        return f"{minutes}m"
    return f"{secs}s"


def format_date_range_label(start_d: date, end_d: date) -> str:
    """Format date range label matching Figma style: 'Aug 17 — Aug 23, 2026'."""
    if start_d.year == end_d.year:
        return f"{start_d.strftime('%b %d')} — {end_d.strftime('%b %d, %Y')}"
    return f"{start_d.strftime('%b %d, %Y')} — {end_d.strftime('%b %d, %Y')}"


class AnalyticsService:
    """Service generating authoritative historical study analytics for authenticated users."""

    @classmethod
    async def get_analytics(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        time_range: str = "7d",
        tz_str: str = "UTC",
    ) -> AnalyticsResponse:
        """Compute aggregated focus analytics for a user over a specified time window."""
        # 1. Resolve user timezone
        try:
            user_tz = zoneinfo.ZoneInfo(tz_str)
        except Exception:
            user_tz = timezone.utc
            tz_str = "UTC"

        now_local = datetime.now(user_tz)
        today_local = now_local.date()

        # 2. Determine local date bounds
        if time_range == "30d":
            days_count = 30
            start_date_local = today_local - timedelta(days=29)
            prev_start_local = start_date_local - timedelta(days=30)
            prev_end_local = start_date_local - timedelta(days=1)
        elif time_range == "all":
            # Find earliest completed session date
            earliest_stmt = (
                select(func.min(StudySession.started_at))
                .where(
                    StudySession.user_id == user_id,
                    StudySession.status == "completed",
                )
            )
            earliest_res = await db.execute(earliest_stmt)
            earliest_dt = earliest_res.scalar()
            if earliest_dt:
                earliest_local = earliest_dt.astimezone(user_tz).date()
                start_date_local = earliest_local
                days_count = max(1, (today_local - start_date_local).days + 1)
            else:
                days_count = 7
                start_date_local = today_local - timedelta(days=6)
            prev_start_local = None
            prev_end_local = None
        else:  # default "7d"
            time_range = "7d"
            days_count = 7
            start_date_local = today_local - timedelta(days=6)
            prev_start_local = start_date_local - timedelta(days=7)
            prev_end_local = start_date_local - timedelta(days=1)

        # Convert local boundaries to UTC datetime for SQL filtering
        start_utc = datetime.combine(start_date_local, time.min, tzinfo=user_tz).astimezone(timezone.utc)
        end_utc = datetime.combine(today_local, time.max, tzinfo=user_tz).astimezone(timezone.utc)

        # 3. Aggregate Summary query across completed sessions
        summary_stmt = (
            select(
                func.count(StudySession.id).label("session_count"),
                func.coalesce(func.sum(StudySession.total_duration_seconds), 0.0).label("total_duration"),
                func.coalesce(func.avg(StudySession.total_duration_seconds), 0.0).label("avg_duration"),
                func.avg(StudySession.focus_score).label("avg_focus"),
                func.coalesce(func.sum(StudySession.distracted_seconds), 0.0).label("total_distracted"),
                func.coalesce(func.sum(StudySession.away_seconds), 0.0).label("total_away"),
            )
            .where(
                StudySession.user_id == user_id,
                StudySession.status == "completed",
                StudySession.started_at >= start_utc,
                StudySession.started_at <= end_utc,
            )
        )
        summary_res = await db.execute(summary_stmt)
        s_count, total_dur, avg_dur, avg_focus_score, total_distracted, total_away = summary_res.one()

        avg_focus_val = float(avg_focus_score) if avg_focus_score is not None else None

        # 4. Discrete Detection Events in this window
        events_stmt = (
            select(
                DetectionEvent.event_type,
                func.count(DetectionEvent.id).label("cnt"),
                func.coalesce(func.sum(DetectionEvent.duration_seconds), 0.0).label("dur"),
            )
            .join(StudySession, DetectionEvent.session_id == StudySession.id)
            .where(
                StudySession.user_id == user_id,
                StudySession.status == "completed",
                StudySession.started_at >= start_utc,
                StudySession.started_at <= end_utc,
            )
            .group_by(DetectionEvent.event_type)
        )
        events_res = await db.execute(events_stmt)
        cat_data = {row[0]: (row[1], float(row[2])) for row in events_res.all()}

        total_event_count = sum(c for c, _ in cat_data.values())
        total_event_duration = sum(d for _, d in cat_data.values())

        # Build category breakdown
        max_cat_dur = max([d for _, d in cat_data.values()], default=0.0)
        breakdown_items = []
        for cat_id, cat_label in CANONICAL_CATEGORIES:
            cnt, dur = cat_data.get(cat_id, (0, 0.0))
            if max_cat_dur > 0:
                pct = round((dur / max_cat_dur) * 100.0, 1)
            elif total_event_count > 0 and cnt > 0:
                pct = 100.0
            else:
                pct = 0.0

            breakdown_items.append(
                CategoryBreakdownItem(
                    id=cat_id,
                    category=cat_id,
                    label=cat_label,
                    count=cnt,
                    duration_seconds=round(dur, 2),
                    duration=format_duration_short(dur),
                    percentWidth=pct,
                )
            )

        # 5. Daily Trend Bucketing
        # Query individual completed sessions in range
        sessions_query = (
            select(
                StudySession.started_at,
                StudySession.total_duration_seconds,
                StudySession.distracted_seconds,
                StudySession.focus_score,
            )
            .where(
                StudySession.user_id == user_id,
                StudySession.status == "completed",
                StudySession.started_at >= start_utc,
                StudySession.started_at <= end_utc,
            )
        )
        sess_res = await db.execute(sessions_query)
        sessions_in_window = sess_res.all()

        # Query events with started_at
        events_query = (
            select(DetectionEvent.started_at)
            .join(StudySession, DetectionEvent.session_id == StudySession.id)
            .where(
                StudySession.user_id == user_id,
                StudySession.status == "completed",
                StudySession.started_at >= start_utc,
                StudySession.started_at <= end_utc,
            )
        )
        evts_res = await db.execute(events_query)
        evts_in_window = evts_res.all()

        # Bucket sessions and events by local calendar date
        daily_sessions: dict[date, list[Any]] = {}
        daily_events_cnt: dict[date, int] = {}

        for started_at, tot_dur, dist_dur, f_score in sessions_in_window:
            loc_date = started_at.astimezone(user_tz).date()
            daily_sessions.setdefault(loc_date, []).append((tot_dur, dist_dur, f_score))

        for (e_started_at,) in evts_in_window:
            loc_date = e_started_at.astimezone(user_tz).date()
            daily_events_cnt[loc_date] = daily_events_cnt.get(loc_date, 0) + 1

        # Generate continuous daily buckets
        daily_trend_items: list[DailyTrendItem] = []
        days_labels: list[str] = []

        curr_d = start_date_local
        while curr_d <= today_local:
            sess_list = daily_sessions.get(curr_d, [])
            d_dur = sum(s[0] for s in sess_list)
            d_dist = sum(s[1] for s in sess_list)
            scores = [float(s[2]) for s in sess_list if s[2] is not None]
            d_focus = round(sum(scores) / len(scores), 1) if scores else None
            d_evts = daily_events_cnt.get(curr_d, 0)

            # Label format: short day for 7d ("Mon"), date for 30d ("Oct 04")
            if time_range == "7d":
                day_lbl = curr_d.strftime("%a")
            else:
                day_lbl = curr_d.strftime("%b %d")

            days_labels.append(day_lbl)
            daily_trend_items.append(
                DailyTrendItem(
                    date=curr_d.isoformat(),
                    label=day_lbl,
                    study_time_seconds=round(d_dur, 2),
                    distracted_seconds=round(d_dist, 2),
                    focus_score=d_focus,
                    distraction_count=d_evts,
                    session_count=len(sess_list),
                )
            )
            curr_d += timedelta(days=1)

        # 6. SVG Trend Line Segments and Points Calculation
        trend_lines: list[TrendLineSegment] = []
        trend_points: list[TrendPoint] = []
        n_days = len(daily_trend_items)

        if n_days > 1:
            x_start = 40.0
            x_end = 880.0
            x_step = (x_end - x_start) / (n_days - 1)

            # Calculate coordinates for each day with focus score
            # Viewbox: 0 0 920 180. Range: score 0% -> y=130, score 100% -> y=30
            coords: list[tuple[int, float, float, float, str, str]] = []
            for idx, item in enumerate(daily_trend_items):
                cx = round(x_start + idx * x_step, 1)
                if item.focus_score is not None:
                    # y range 30 to 130
                    cy = round(130.0 - (item.focus_score / 100.0) * 100.0, 1)
                    coords.append((idx, cx, cy, item.focus_score, item.date, item.label))
                    trend_points.append(
                        TrendPoint(
                            cx=cx,
                            cy=cy,
                            score=item.focus_score,
                            date=item.date,
                            day=item.label,
                        )
                    )

            # Connect consecutive scored days with line segments
            for i in range(len(coords) - 1):
                idx1, cx1, cy1, _, _, _ = coords[i]
                idx2, cx2, cy2, _, _, _ = coords[i + 1]
                # If they are reasonably adjacent, draw connecting segment
                trend_lines.append(
                    TrendLineSegment(
                        x1=cx1,
                        y1=cy1,
                        x2=cx2,
                        y2=cy2,
                        startPoint=(i == 0),
                        endPoint=(i == len(coords) - 2),
                    )
                )

        # 7. Previous period comparison
        change_text = ""
        if prev_start_local and prev_end_local:
            prev_start_utc = datetime.combine(prev_start_local, time.min, tzinfo=user_tz).astimezone(timezone.utc)
            prev_end_utc = datetime.combine(prev_end_local, time.max, tzinfo=user_tz).astimezone(timezone.utc)
            prev_stmt = (
                select(func.avg(StudySession.focus_score))
                .where(
                    StudySession.user_id == user_id,
                    StudySession.status == "completed",
                    StudySession.started_at >= prev_start_utc,
                    StudySession.started_at <= prev_end_utc,
                )
            )
            prev_res = await db.execute(prev_stmt)
            prev_score = prev_res.scalar()
            if prev_score is not None and avg_focus_val is not None:
                diff = round(avg_focus_val - float(prev_score), 1)
                sign = "+" if diff > 0 else ""
                period_label = "last week" if time_range == "7d" else "last month"
                change_text = f"{sign}{int(diff) if diff.is_integer() else diff}% vs {period_label}"

        # 8. Comparison Card (Today / This week / This month)
        # Query stats for Today
        today_start_utc = datetime.combine(today_local, time.min, tzinfo=user_tz).astimezone(timezone.utc)
        today_end_utc = datetime.combine(today_local, time.max, tzinfo=user_tz).astimezone(timezone.utc)

        today_stmt = (
            select(
                func.coalesce(func.sum(StudySession.total_duration_seconds), 0.0),
                func.avg(StudySession.focus_score),
            )
            .where(
                StudySession.user_id == user_id,
                StudySession.status == "completed",
                StudySession.started_at >= today_start_utc,
                StudySession.started_at <= today_end_utc,
            )
        )
        today_res = await db.execute(today_stmt)
        today_dur, today_score = today_res.one()

        # Query stats for This Week (last 7 days)
        week_start_utc = datetime.combine(today_local - timedelta(days=6), time.min, tzinfo=user_tz).astimezone(timezone.utc)
        week_stmt = (
            select(
                func.coalesce(func.sum(StudySession.total_duration_seconds), 0.0),
                func.avg(StudySession.focus_score),
            )
            .where(
                StudySession.user_id == user_id,
                StudySession.status == "completed",
                StudySession.started_at >= week_start_utc,
                StudySession.started_at <= today_end_utc,
            )
        )
        week_res = await db.execute(week_stmt)
        week_dur, week_score = week_res.one()

        # Query stats for This Month (last 30 days)
        month_start_utc = datetime.combine(today_local - timedelta(days=29), time.min, tzinfo=user_tz).astimezone(timezone.utc)
        month_stmt = (
            select(
                func.coalesce(func.sum(StudySession.total_duration_seconds), 0.0),
                func.avg(StudySession.focus_score),
            )
            .where(
                StudySession.user_id == user_id,
                StudySession.status == "completed",
                StudySession.started_at >= month_start_utc,
                StudySession.started_at <= today_end_utc,
            )
        )
        month_res = await db.execute(month_stmt)
        month_dur, month_score = month_res.one()

        comp_rows = [
            ComparisonRow(
                id="comp-today",
                period="Today",
                score=f"{round(float(today_score))}%" if today_score is not None else "—",
                duration=format_duration_short(today_dur),
            ),
            ComparisonRow(
                id="comp-week",
                period="This week",
                score=f"{round(float(week_score))}%" if week_score is not None else "—",
                duration=format_duration_short(week_dur),
            ),
            ComparisonRow(
                id="comp-month",
                period="This month",
                score=f"{round(float(month_score))}%" if month_score is not None else "—",
                duration=format_duration_short(month_dur),
            ),
        ]

        # Badge text and title
        badge_text = "This week" if time_range == "7d" else ("Last 30 days" if time_range == "30d" else "All time")
        score_text = f"{round(avg_focus_val)}%" if avg_focus_val is not None else "—"

        subtitle_text = (
            "Weekly focus score · last 7 days"
            if time_range == "7d"
            else ("Monthly focus score · last 30 days" if time_range == "30d" else "Overall focus score · all time")
        )

        return AnalyticsResponse(
            range=time_range,
            start_date=start_date_local.isoformat(),
            end_date=today_local.isoformat(),
            timezone=tz_str,
            summary=AnalyticsSummary(
                total_study_time_seconds=round(float(total_dur), 2),
                average_session_duration_seconds=round(float(avg_dur), 2),
                average_focus_score=round(avg_focus_val, 2) if avg_focus_val is not None else None,
                total_distracted_seconds=round(float(total_distracted), 2),
                total_away_seconds=round(float(total_away), 2),
                total_distractions=total_event_count,
                completed_sessions_count=s_count,
            ),
            trend=AnalyticsTrend(
                title="Focus Score Trend",
                subtitle=subtitle_text,
                badgeText=badge_text,
                score=score_text,
                changeText=change_text,
                days=days_labels,
                data=daily_trend_items,
                trendLines=trend_lines,
                points=trend_points,
            ),
            breakdown=AnalyticsBreakdown(
                title="Distraction Breakdown",
                categories=breakdown_items,
                footerSummary=f"{total_event_count} detected events · {format_duration_short(total_event_duration)} distracted",
                total_distraction_seconds=round(total_event_duration, 2),
                total_events=total_event_count,
            ),
            comparison=AnalyticsComparison(
                title="Comparison",
                rows=comp_rows,
                dateRange=format_date_range_label(start_date_local, today_local),
            ),
        )
