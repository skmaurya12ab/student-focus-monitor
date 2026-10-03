"""Tests for the dedicated Account and Profile endpoints."""
import pytest
from httpx import AsyncClient, ASGITransport

from app.db.session import get_async_session
from app.main import app


@pytest.mark.asyncio
async def test_get_account_details(db_session):
    """Verify /api/account returns user profile and linked Google identities."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post(
            "/api/auth/google",
            json={"id_token": "mock_google_id_token_sarah"},
        )
        token = login_res.json()["access_token"]

        account_res = await client.get(
            "/api/account",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert account_res.status_code == 200
        account_data = account_res.json()

        assert account_data["user"]["display_name"] == "Student Sarah"
        assert account_data["user"]["email"] == "sarah@example.com"
        assert len(account_data["identities"]) == 1
        assert account_data["identities"][0]["provider"] == "google"
        assert account_data["identities"][0]["provider_subject"] == "google-sub-sarah"
        assert account_data["active_sessions_count"] == 0

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_profile_display_name(db_session):
    """Verify /api/account PATCH updates user display name."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post(
            "/api/auth/google",
            json={"id_token": "mock_google_id_token_jordan"},
        )
        token = login_res.json()["access_token"]

        patch_res = await client.patch(
            "/api/account",
            headers={"Authorization": f"Bearer {token}"},
            json={"display_name": "Jordan Smith"},
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["display_name"] == "Jordan Smith"

        # Verify updated info returned in /api/account
        account_res = await client.get(
            "/api/account",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert account_res.status_code == 200
        assert account_res.json()["user"]["display_name"] == "Jordan Smith"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_profile_empty_name_validation(db_session):
    """Verify /api/account PATCH rejects empty or whitespace-only display name."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post(
            "/api/auth/google",
            json={"id_token": "mock_google_id_token_chris"},
        )
        token = login_res.json()["access_token"]

        patch_res = await client.patch(
            "/api/account",
            headers={"Authorization": f"Bearer {token}"},
            json={"display_name": "   "},
        )
        # Should fail with 422 Unprocessable Entity
        assert patch_res.status_code == 422

    app.dependency_overrides.clear()
