"""Historical Focus Analytics API endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.session import get_async_session
from app.schemas.analytics import AnalyticsResponse
from app.services.auth_service import get_current_user
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get(
    "",
    response_model=AnalyticsResponse,
    summary="Retrieve historical focus analytics for authenticated user",
)
async def get_analytics(
    range: str = Query("7d", pattern="^(7d|30d|all)$", description="Date range: '7d', '30d', or 'all'"),
    tz: str = Query("UTC", description="User local IANA timezone name (e.g. 'America/New_York', 'Asia/Kolkata')"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> AnalyticsResponse:
    """Retrieve aggregated focus analytics, trend data, and category breakdown for the authenticated user.
    
    All metrics are computed exclusively from the user's completed study sessions and persisted detection events.
    """
    return await AnalyticsService.get_analytics(
        db,
        current_user.id,
        time_range=range,
        tz_str=tz,
    )
