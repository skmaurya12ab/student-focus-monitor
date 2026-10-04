"""End-to-end integration test proving that saving user settings controls live detection alert activation."""
import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from app.db.models.study_session import StudySession
from app.db.models.user_settings import UserSettings
from app.db.session import get_async_session
from app.detection.config import ALERT_PHONE_USE
from app.main import app
from app.services.detection_runtime_service import detection_runtime_manager
from app.services.settings_service import SettingsService


@pytest.mark.asyncio
async def test_settings_save_and_runtime_integration(db_session):
    """
    Full end-to-end trace:
    1. Authenticated user changes alert threshold to phone_use = 2.0 seconds
    2. Threshold is saved via PATCH /api/settings
    3. User starts a study session
    4. Live detector runtime is initialized via SettingsService
    5. Runtime receives the saved 2.0s threshold
    6. Sustained detector condition is fed to it
    7. Alert activates at 2.0s (not 6.0s, not 20.0s)
    """
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Step 1 & 2: Login and save custom threshold (phone_use = 2.0s)
        login_res = await client.post(
            "/api/auth/dev-login",
            json={"email": "e2e_settings@example.com", "display_name": "E2E Settings User"},
        )
        assert login_res.status_code == 200
        user_id = uuid.UUID(login_res.json()["user"]["id"])

        patch_res = await client.patch(
            "/api/settings",
            json={"phone_use_delay_seconds": 2.0, "sound_alerts_enabled": True},
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["phone_use_delay_seconds"] == 2.0

        # Step 3: Start study session
        session_res = await client.post("/api/sessions", json={})
        assert session_res.status_code == 201
        session_id = uuid.UUID(session_res.json()["id"])

        # Step 4: When WebSocket connects, it queries SettingsService and passes config to runtime
        user_settings = await SettingsService.get_user_settings(db_session, user_id)
        assert user_settings.phone_use_delay_seconds == 2.0

        detector_config = SettingsService.build_detector_config(user_settings)
        runtime = await detection_runtime_manager.get_or_create_runtime(
            session_id, user_id, config=detector_config
        )

        # Step 5: Verify runtime has the saved 2.0s threshold (not 20s or 6s)
        phone_tracker = runtime.detector.trackers.trackers[ALERT_PHONE_USE]
        assert phone_tracker.delay == 2.0

        # Step 6 & 7: Feed sustained condition and verify alert triggers at 2.0s
        t0 = 5000.0
        # t = 0.0s
        res_0 = phone_tracker.update(True, now=t0)
        assert res_0.active is False

        # t = 1.0s (< 2.0s) -> still inactive
        res_1 = phone_tracker.update(True, now=t0 + 1.0)
        assert res_1.active is False

        # t = 2.0s (== configured 2.0s threshold) -> ACTIVES IMMEDIATELY!
        res_2 = phone_tracker.update(True, now=t0 + 2.0)
        assert res_2.active is True
        assert res_2.just_started is True

        # Clean up
        await detection_runtime_manager.stop_session_detection(session_id, db=db_session)

    app.dependency_overrides.clear()
