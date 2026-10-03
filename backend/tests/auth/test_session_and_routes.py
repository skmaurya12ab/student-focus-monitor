"""Tests for application sessions, JWT handling, and protected routes."""
from datetime import timedelta
import pytest
from httpx import AsyncClient, ASGITransport

from app.core.security import create_access_token, decode_access_token
from app.db.session import get_async_session
from app.main import app


@pytest.mark.asyncio
async def test_dev_login_and_me_endpoint(db_session):
    """Verify development login returns token and /api/auth/me yields authenticated user profile."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Dev login
        login_res = await client.post(
            "/api/auth/dev-login",
            json={
                "email": "test-student@example.com",
                "display_name": "Test Student",
                "google_sub": "dev-sub-9999",
            },
        )
        assert login_res.status_code == 200
        token_data = login_res.json()
        token = token_data["access_token"]
        user_id = token_data["user"]["id"]

        # Call /api/auth/me with Bearer token
        me_res = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert me_data["id"] == user_id
        assert me_data["display_name"] == "Test Student"
        assert me_data["email"] == "test-student@example.com"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_me_unauthenticated_returns_401(db_session):
    """Verify /api/auth/me rejects requests missing the Authorization header."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/auth/me")
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_me_invalid_token_returns_401(db_session):
    """Verify /api/auth/me rejects invalid or forged JWT tokens."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid.token.signature"},
        )
        assert response.status_code == 401

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_expired_jwt_token_rejected(db_session):
    """Verify expired JWT tokens cannot authenticate."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create user via dev-login
        login_res = await client.post(
            "/api/auth/dev-login",
            json={"email": "expired@example.com", "display_name": "Expired User"},
        )
        user_uuid = login_res.json()["user"]["id"]

        # Generate an intentionally expired token
        import uuid
        expired_token = create_access_token(
            user_id=uuid.UUID(user_uuid),
            expires_delta=timedelta(seconds=-10),
        )

        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code == 401

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_logout_endpoint(db_session):
    """Verify /api/auth/logout succeeds for authenticated sessions."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post(
            "/api/auth/dev-login",
            json={"email": "logout-test@example.com", "display_name": "Logout User"},
        )
        token = login_res.json()["access_token"]

        logout_res = await client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert logout_res.status_code == 200
        assert logout_res.json()["status"] == "success"

    app.dependency_overrides.clear()
