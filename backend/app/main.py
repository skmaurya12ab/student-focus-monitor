"""FastAPI main application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Centralized CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes with /api prefix
app.include_router(api_router, prefix="/api")


@app.get("/")
def read_root():
    """Root endpoint for quick service identification."""
    return {
        "service": settings.PROJECT_NAME,
        "status": "running",
        "docs": "/docs",
        "health": "/api/health",
    }
