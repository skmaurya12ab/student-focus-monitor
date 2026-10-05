"""Tests for leakage prevention, grouped user splitting, and reproducibility."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
import uuid

from ml.dataset.config import DatasetConfig
from ml.dataset.extract import ExtractedSession
from ml.dataset.splits import compute_grouped_user_splits


def make_sessions(num_users: int, sessions_per_user: int = 2) -> dict[uuid.UUID, ExtractedSession]:
    sessions: dict[uuid.UUID, ExtractedSession] = {}
    now = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)

    for u_idx in range(num_users):
        u_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"user-{u_idx}")
        for s_idx in range(sessions_per_user):
            s_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"session-{u_idx}-{s_idx}")
            sessions[s_id] = ExtractedSession(
                id=s_id,
                user_id=u_id,
                status="completed",
                started_at=now,
                ended_at=now,
                total_duration_seconds=100.0,
                focused_seconds=80.0,
                distracted_seconds=20.0,
                away_seconds=0.0,
                focus_score=80.0,
                detector_version="v4",
                feature_schema_version="telemetry_v2",
            )
    return sessions


def test_grouped_user_splitting_prevents_leakage():
    """Verify that users and sessions are strictly disjoint across train/val/test."""
    sessions = make_sessions(num_users=6, sessions_per_user=3)
    config = DatasetConfig(train_ratio=0.70, val_ratio=0.15, test_ratio=0.15, random_seed=42)

    res = compute_grouped_user_splits(sessions, config)
    assert res.is_split_valid is True
    assert res.warning is None

    # Group users by split
    train_users = {u for u, s in res.user_splits.items() if s == "train"}
    val_users = {u for u, s in res.user_splits.items() if s == "val"}
    test_users = {u for u, s in res.user_splits.items() if s == "test"}

    # Assert zero user leakage
    assert not (train_users & val_users)
    assert not (train_users & test_users)
    assert not (val_users & test_users)
    assert len(train_users) >= 1
    assert len(val_users) >= 1
    assert len(test_users) >= 1

    # Group sessions by split
    train_sessions = {s for s, split in res.session_splits.items() if split == "train"}
    val_sessions = {s for s, split in res.session_splits.items() if split == "val"}
    test_sessions = {s for s, split in res.session_splits.items() if split == "test"}

    # Assert zero session leakage
    assert not (train_sessions & val_sessions)
    assert not (train_sessions & test_sessions)
    assert not (val_sessions & test_sessions)

    # Every session of a user must match the user's split
    for s_id, s in sessions.items():
        assert res.session_splits[s_id] == res.user_splits[s.user_id]


def test_split_reproducibility():
    """Verify identical seeds produce identical splits."""
    sessions = make_sessions(num_users=5, sessions_per_user=2)
    cfg1 = DatasetConfig(random_seed=123)
    cfg2 = DatasetConfig(random_seed=123)

    res1 = compute_grouped_user_splits(sessions, cfg1)
    res2 = compute_grouped_user_splits(sessions, cfg2)

    assert res1.user_splits == res2.user_splits
    assert res1.session_splits == res2.session_splits


def test_insufficient_users_reports_warning_honestly():
    """When fewer than min_users_for_split exist, pipeline must report warning and not fabricate valid split."""
    sessions = make_sessions(num_users=2, sessions_per_user=2)
    config = DatasetConfig(min_users_for_split=3)

    res = compute_grouped_user_splits(sessions, config)
    assert res.is_split_valid is False
    assert "Insufficient distinct users" in res.warning
    # All sessions assigned to 'all'
    assert all(s == "all" for s in res.session_splits.values())
    assert all(u == "all" for u in res.user_splits.values())
