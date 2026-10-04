"""Tests for Settings API (GET and PATCH /api/settings)."""
import pytest
from httpx import AsyncClient, ASGITransport

from app.db.session import get_async_session
from app.main import app


@pytest.mark.asyncio
async def test_get_settings_authenticated(db_session):
    """Verify authenticated user can fetch their settings with authoritative defaults."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Dev login
        login_res = await client.post(
            "/api/auth/dev-login",
            json={"email": "settings_user@example.com", "display_name": "Settings Tester"},
        )
        assert login_res.status_code == 200

        # Fetch settings
        res = await client.get("/api/settings")
        assert res.status_code == 200
        data = res.json()

        assert data["yawning_delay_seconds"] == 2.0
        assert data["phone_use_delay_seconds"] == 6.0
        assert data["leaning_back_delay_seconds"] == 8.0
        assert data["drowsy_delay_seconds"] == 4.0
        assert data["away_from_desk_delay_seconds"] == 10.0
        assert data["looking_away_delay_seconds"] == 10.0
        assert "sound_alerts_enabled" in data
        assert "banner_alerts_enabled" in data
        assert "camera_device" in data
        assert "preview_quality" in data

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_patch_settings_updates_delays_and_notifications(db_session):
    """Verify updating persistence delays and notification toggles persists to database."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Dev login
        login_res = await client.post(
            "/api/auth/dev-login",
            json={"email": "patch_user@example.com", "display_name": "Patch User"},
        )
        assert login_res.status_code == 200

        # Patch settings with custom delays
        patch_payload = {
            "phone_use_delay_seconds": 2.5,
            "yawning_delay_seconds": 1.5,
            "leaning_back_delay_seconds": 5.0,
            "drowsy_delay_seconds": 3.0,
            "away_from_desk_delay_seconds": 7.0,
            "sound_alerts_enabled": True,
            "banner_alerts_enabled": True,
            "camera_device": "External USB Camera - 1080p",
        }
        patch_res = await client.patch("/api/settings", json=patch_payload)
        assert patch_res.status_code == 200
        updated = patch_res.json()

        assert updated["phone_use_delay_seconds"] == 2.5
        assert updated["yawning_delay_seconds"] == 1.5
        assert updated["leaning_back_delay_seconds"] == 5.0
        assert updated["drowsy_delay_seconds"] == 3.0
        assert updated["away_from_desk_delay_seconds"] == 7.0
        assert updated["sound_alerts_enabled"] is True
        assert updated["banner_alerts_enabled"] is True
        assert updated["camera_device"] == "External USB Camera - 1080p"

        # Verify persistent read back via GET
        get_res = await client.get("/api/settings")
        assert get_res.status_code == 200
        persisted = get_res.json()
        assert persisted["phone_use_delay_seconds"] == 2.5
        assert persisted["sound_alerts_enabled"] is True

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_patch_settings_rejects_negative_or_invalid_delays(db_session):
    """Verify validation: delays must be >= 0.5s."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Dev login
        await client.post(
            "/api/auth/dev-login",
            json={"email": "validation_user@example.com", "display_name": "Validation User"},
        )

        # Negative delay
        res = await client.patch("/api/settings", json={"phone_use_delay_seconds": -5.0})
        assert res.status_code == 422

        # Too small delay (< 0.5s)
        res_zero = await client.patch("/api/settings", json={"phone_use_delay_seconds": 0.1})
        assert res_zero.status_code == 422

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_settings_unauthenticated_returns_401(db_session):
    """Verify unauthenticated requests to /api/settings are rejected with 401."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        get_res = await client.get("/api/settings")
        assert get_res.status_code == 401

        patch_res = await client.patch("/api/settings", json={"phone_use_delay_seconds": 3.0})
        assert patch_res.status_code == 401

    app.dependency_overrides.clear()
