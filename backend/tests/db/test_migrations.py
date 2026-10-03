"""Tests for Alembic migrations: upgrade head, downgrade base, and round-trip verification."""
import os
import pytest
from sqlalchemy import create_engine, inspect
from alembic.config import Config
from alembic import command


MIGRATION_TEST_DB_URL = os.environ.get(
    "MIGRATION_TEST_DB_URL",
    "postgresql://localhost:5433/sfm_migration_test"
)


EXPECTED_TABLES = {
    "users",
    "auth_identities",
    "user_settings",
    "study_sessions",
    "detection_events",
    "telemetry_samples",
    "session_feedback",
}


@pytest.fixture(scope="module")
def alembic_config():
    """Return an Alembic Config instance configured for sfm_migration_test database."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    ini_path = os.path.join(base_dir, "alembic.ini")
    cfg = Config(ini_path)
    cfg.set_main_option("sqlalchemy.url", MIGRATION_TEST_DB_URL)
    # Also set env var for alembic env.py
    os.environ["DATABASE_URL"] = MIGRATION_TEST_DB_URL
    return cfg


@pytest.fixture(scope="module")
def migration_engine():
    """Create a synchronous engine for inspecting migration test database."""
    from app.db.session import get_sync_database_url
    sync_url = get_sync_database_url(MIGRATION_TEST_DB_URL)
    engine = create_engine(sync_url)
    yield engine
    engine.dispose()


def test_migration_lifecycle_upgrade_downgrade_roundtrip(alembic_config, migration_engine):
    """Verify upgrade head -> downgrade base -> upgrade head round-trip on fresh database."""
    # 1. Start fresh: downgrade to base if anything exists
    try:
        command.downgrade(alembic_config, "base")
    except Exception:
        pass

    # 2. Test UPGRADE HEAD
    command.upgrade(alembic_config, "head")

    inspector = inspect(migration_engine)
    tables_after_upgrade = set(inspector.get_table_names())
    assert EXPECTED_TABLES.issubset(tables_after_upgrade), (
        f"Missing expected tables after upgrade! Found: {tables_after_upgrade}"
    )
    assert "alembic_version" in tables_after_upgrade

    # Verify foreign keys and indexes on study_sessions
    fks = inspector.get_foreign_keys("study_sessions")
    fk_tables = {fk["referred_table"] for fk in fks}
    assert "users" in fk_tables

    indexes = {idx["name"] for idx in inspector.get_indexes("study_sessions")}
    assert "ix_study_sessions_user_started" in indexes

    # 3. Test DOWNGRADE BASE
    command.downgrade(alembic_config, "base")

    inspector = inspect(migration_engine)
    tables_after_downgrade = set(inspector.get_table_names())
    for expected in EXPECTED_TABLES:
        assert expected not in tables_after_downgrade, (
            f"Table {expected} was not dropped by downgrade base!"
        )

    # 4. Test ROUND-TRIP: UPGRADE HEAD AGAIN
    command.upgrade(alembic_config, "head")

    inspector = inspect(migration_engine)
    tables_after_reupgrade = set(inspector.get_table_names())
    assert EXPECTED_TABLES.issubset(tables_after_reupgrade), (
        f"Missing expected tables after round-trip upgrade! Found: {tables_after_reupgrade}"
    )
