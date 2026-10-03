"""Health check endpoint router."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def get_health():
    """Verify backend availability. Returns HTTP 200 with status ok."""
    return {"status": "ok"}
