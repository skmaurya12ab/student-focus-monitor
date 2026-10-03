"""Tests verifying database privacy boundaries: zero media storage in schema and models."""
from sqlalchemy import inspect
from app.db.base import Base
from app.db.models import TelemetrySample


PROHIBITED_MEDIA_SUBSTRINGS = [
    "image",
    "video",
    "audio",
    "buffer",
    "bytes",
    "media",
    "photo",
    "picture",
    "recording",
    "stream",
    "webcam_feed",
]


def test_telemetry_model_has_no_media_fields():
    """Verify TelemetrySample model contains no columns or attributes storing media."""
    column_names = [col.name for col in TelemetrySample.__table__.columns]

    for col in column_names:
        lower_col = col.lower()
        # frame_index is a discrete frame counter, which is allowed; but frame_buffer or frame_bytes is prohibited
        if lower_col == "frame_index":
            continue

        for prohibited in PROHIBITED_MEDIA_SUBSTRINGS:
            assert prohibited not in lower_col, (
                f"Prohibited media field '{col}' detected in TelemetrySample model! "
                f"Student Focus Monitor database must never store media."
            )


def test_all_database_models_privacy_boundary():
    """Verify across all tables in Base.metadata that no table contains media or audio/video payload columns."""
    for table_name, table in Base.metadata.tables.items():
        if table_name == "alembic_version":
            continue
        for column in table.columns:
            col_name = column.name.lower()
            if col_name in ("camera_device", "frame_index"):
                # camera_device is user device preference string ("Integrated Camera")
                # frame_index is integer counter
                continue
            for prohibited in PROHIBITED_MEDIA_SUBSTRINGS:
                assert prohibited not in col_name, (
                    f"Prohibited media field '{column.name}' found in table '{table_name}'!"
                )


def test_postgresql_schema_inspection_privacy(sync_test_engine):
    """Verify live PostgreSQL schema columns for telemetry_samples contain zero media columns."""
    inspector = inspect(sync_test_engine)
    columns = inspector.get_columns("telemetry_samples")
    column_names = [col["name"].lower() for col in columns]

    for col in column_names:
        if col == "frame_index":
            continue
        for prohibited in PROHIBITED_MEDIA_SUBSTRINGS:
            assert prohibited not in col, (
                f"Prohibited media column '{col}' discovered in PostgreSQL telemetry_samples table!"
            )


def test_telemetry_column_types_are_strictly_structured(sync_test_engine):
    """Verify live PostgreSQL column types for telemetry_samples are strictly numeric, boolean, uuid, datetime, varchar, or jsonb."""
    inspector = inspect(sync_test_engine)
    columns = inspector.get_columns("telemetry_samples")

    allowed_pg_type_names = {
        "UUID",
        "TIMESTAMP",
        "DOUBLE PRECISION",
        "INTEGER",
        "BOOLEAN",
        "VARCHAR",
        "JSONB",
    }

    for col in columns:
        type_str = str(col["type"]).upper()
        # Match type category
        matched = any(allowed in type_str for allowed in allowed_pg_type_names)
        assert matched, (
            f"Unexpected or unsafe column type '{type_str}' on column '{col['name']}' in telemetry_samples! "
            f"Only numerical, boolean, structured JSON, timestamp, UUID, or short version strings are allowed."
        )
