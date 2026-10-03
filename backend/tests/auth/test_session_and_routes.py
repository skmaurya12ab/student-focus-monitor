"""Tests for application sessions, HttpOnly cookie handling, and protected routes."""
from datetime import timedelta
import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from app.core.security import create_access_token
from app.db.session import get_async_session
from app.main import app


@pytest.mark.asyncio
async def test_dev_login_and_cookie_session_flow(db_session):
    """Verify development login sets HttpOnly sfm_session cookie and /api/auth/me authenticates via cookie."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Dev login sets HttpOnly session cookie
        login_res = await client.post(
            "/api/auth/dev-login",
            json={
                "email": "test-student@example.com",
                "display_name": "Test Student",
                "google_sub": "dev-sub-9999",
            },
        )
        assert login_res.status_code == 200
        assert "sfm_session" in client.cookies
        login_data = login_res.json()
        assert login_data["status"] == "success"
        user_id = login_data["user"]["id"]

        # Call /api/auth/me with NO Authorization header - cookie authenticates session
        me_res = await client.get("/api/auth/me")
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert me_data["id"] == user_id
        assert me_data["display_name"] == "Test Student"
        assert me_data["email"] == "test-student@example.com"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_me_unauthenticated_returns_401(db_session):
    """Verify /api/auth/me rejects requests missing both session cookie and Authorization header."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/auth/me")
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_me_invalid_cookie_returns_401(db_session):
    """Verify /api/auth/me rejects invalid or forged session cookie."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.cookies.set("sfm_session", "invalid.jwt.signature")
        response = await client.get("/api/auth/me")
        assert response.status_code == 401

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_expired_session_cookie_rejected(db_session):
    """Verify expired session cookies cannot authenticate."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create user via dev-login
        login_res = await client.post(
            "/api/auth/dev-login",
            json={"email": "expired@example.com", "display_name": "Expired User"},
        )
        user_uuid = login_res.json()["user"]["id"]

        # Generate an intentionally expired session token
        expired_token = create_access_token(
            user_id=uuid.UUID(user_uuid),
            expires_delta=timedelta(seconds=-10),
        )

        client.cookies.set("sfm_session", expired_token)
        response = await client.get("/api/auth/me")
        assert response.status_code == 401

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_logout_clears_cookie_session(db_session):
    """Verify /api/auth/logout deletes the sfm_session cookie and invalidates session."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post(
            "/api/auth/dev-login",
            json={"email": "logout-test@example.com", "display_name": "Logout User"},
        )
        assert login_res.status_code == 200
        assert "sfm_session" in client.cookies

        # Logout clears session cookie
        logout_res = await client.post("/api/auth/logout")
        assert logout_res.status_code == 200
        assert logout_res.json()["status"] == "success"

        # Subsequent authenticated request is rejected (401)
        me_res = await client.get("/api/auth/me")
        assert me_res.status_code == 401

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_bearer_token_fallback_support(db_session):
    """Verify Bearer token Authorization header is supported as fallback for programmatic clients."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post(
            "/api/auth/dev-login",
            json={"email": "bearer-fallback@example.com", "display_name": "Bearer User"},
        )
        user_id = login_res.json()["user"]["id"]
        token = create_access_token(user_id=uuid.UUID(user_id))

        # Separate client without cookie
        async with AsyncClient(transport=transport, base_url="http://test") as api_client:
            me_res = await api_client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert me_res.status_code == 200
            assert me_res.json()["id"] == user_id

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cors_preflight_and_credentials_localhost_5174():
    """Verify CORS preflight and request headers for frontend development origin http://localhost:5174."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Preflight OPTIONS on protected endpoint
        preflight_res = await client.options(
            "/api/account",
            headers={
                "Origin": "http://localhost:5174",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert preflight_res.status_code == 200
        assert preflight_res.headers.get("access-control-allow-origin") == "http://localhost:5174"
        assert preflight_res.headers.get("access-control-allow-credentials") == "true"

        # Simple request with Origin
        health_res = await client.get(
            "/api/health",
            headers={"Origin": "http://localhost:5174"},
        )
        assert health_res.status_code == 200
        assert health_res.headers.get("access-control-allow-origin") == "http://localhost:5174"
        assert health_res.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_account_unauthenticated_returns_401(db_session):
    """Verify /api/account returns 401 when accessed without session cookie."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/account")
        assert res.status_code == 401

    app.dependency_overrides.clear()


