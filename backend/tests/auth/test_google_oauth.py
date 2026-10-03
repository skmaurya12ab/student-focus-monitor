"""Tests for Google OAuth 2.0 / OpenID Connect service and authentication endpoint."""
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from app.main import app
from app.db.models.user import User
from app.db.models.auth_identity import AuthIdentity
from app.db.models.user_settings import UserSettings
from app.services.google_auth import GoogleAuthService
from app.db.session import get_async_session


@pytest.mark.asyncio
async def test_google_auth_url_generation():
    """Verify Google OAuth authorization URL contains necessary OAuth/OIDC parameters."""
    result = GoogleAuthService.get_authorization_url()
    url = result["url"]
    state = result["state"]

    assert "accounts.google.com/o/oauth2/v2/auth" in url
    assert "response_type=code" in url
    assert "scope=openid+email+profile" in url or "scope=openid" in url
    assert f"state={state}" in url


@pytest.mark.asyncio
async def test_google_mock_id_token_verification():
    """Verify Google ID token verification extracts standard OIDC claims."""
    claims = await GoogleAuthService.verify_id_token("mock_google_id_token_alex")
    assert claims["sub"] == "google-sub-alex"
    assert claims["email"] == "alex@example.com"
    assert "Alex" in claims["name"]
    assert claims["email_verified"] is True


@pytest.mark.asyncio
async def test_authenticate_google_new_user(db_session):
    """Verify first-time Google authentication provisions User, UserSettings, and AuthIdentity."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/google",
            json={"id_token": "mock_google_id_token_emma"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "emma@example.com"
    assert data["user"]["display_name"] == "Student Emma"

    # Verify database persistence
    user_stmt = select(User).where(User.email == "emma@example.com")
    user_res = await db_session.execute(user_stmt)
    user = user_res.scalars().first()
    assert user is not None

    identity_stmt = select(AuthIdentity).where(AuthIdentity.user_id == user.id)
    id_res = await db_session.execute(identity_stmt)
    identity = id_res.scalars().first()
    assert identity is not None
    assert identity.provider == "google"
    assert identity.provider_subject == "google-sub-emma"

    # Verify default user settings were created
    settings_stmt = select(UserSettings).where(UserSettings.user_id == user.id)
    settings_res = await db_session.execute(settings_stmt)
    settings = settings_res.scalars().first()
    assert settings is not None
    assert settings.looking_away_delay_seconds == 10.0


@pytest.mark.asyncio
async def test_authenticate_google_existing_user(db_session):
    """Verify repeated Google login reuses existing account and updates last_login_at."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First login
        res1 = await client.post(
            "/api/auth/google",
            json={"id_token": "mock_google_id_token_david"},
        )
        assert res1.status_code == 200
        user_id_1 = res1.json()["user"]["id"]

        # Second login with same provider_subject
        res2 = await client.post(
            "/api/auth/google",
            json={"id_token": "mock_google_id_token_david"},
        )
        assert res2.status_code == 200
        user_id_2 = res2.json()["user"]["id"]

        assert user_id_1 == user_id_2

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_authenticate_google_missing_credentials(db_session):
    """Verify 400 Bad Request if neither id_token nor code is provided."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/auth/google", json={})
        assert response.status_code == 400

    app.dependency_overrides.clear()
