"""Leakage-safe grouped user splitting module."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Mapping, Sequence
import uuid

from ml.dataset.config import DatasetConfig
from ml.dataset.extract import ExtractedSession, ExtractedUser


@dataclass
class SplitAssignment:
    """Grouped assignment of users and sessions to train/val/test splits."""

    # user_id -> split name ("train", "val", "test", or "all")
    user_splits: dict[uuid.UUID, str]
    # session_id -> split name
    session_splits: dict[uuid.UUID, str]

    is_split_valid: bool
    warning: Optional[str] = None

    # Counts
    user_counts: dict[str, int] = field(default_factory=dict)
    session_counts: dict[str, int] = field(default_factory=dict)


def compute_grouped_user_splits(
    sessions: Mapping[uuid.UUID, ExtractedSession],
    config: DatasetConfig,
) -> SplitAssignment:
    """
    Compute leakage-safe grouped split by user.
    All sessions belonging to the same user remain strictly in one split.
    Fails safely if there are fewer distinct users than min_users_for_split.
    """
    # Group sessions by user_id
    sessions_by_user: dict[uuid.UUID, list[uuid.UUID]] = {}
    for sid, s in sessions.items():
        sessions_by_user.setdefault(s.user_id, []).append(sid)

    distinct_users = sorted(list(sessions_by_user.keys()))
    num_users = len(distinct_users)

    if num_users < config.min_users_for_split:
        warning_msg = (
            f"Insufficient distinct users for leakage-safe multi-user train/validation/test split. "
            f"Found {num_users} distinct user(s), minimum required is {config.min_users_for_split}."
        )
        # Assign all to 'all' split without pretending a valid 3-way generalization split exists
        user_splits = {u: "all" for u in distinct_users}
        session_splits = {s: "all" for s in sessions.keys()}
        return SplitAssignment(
            user_splits=user_splits,
            session_splits=session_splits,
            is_split_valid=False,
            warning=warning_msg,
            user_counts={"all": num_users},
            session_counts={"all": len(sessions)},
        )

    # Deterministic seeded shuffle of users
    rng = random.Random(config.random_seed)
    shuffled_users = list(distinct_users)
    rng.shuffle(shuffled_users)

    # Compute partition sizes ensuring at least 1 user per split
    n_test = max(1, int(round(num_users * config.test_ratio)))
    n_val = max(1, int(round(num_users * config.val_ratio)))
    # If val + test takes up all or more users, adjust so train gets at least 1
    if n_val + n_test >= num_users:
        if n_test > 1:
            n_test -= 1
        elif n_val > 1:
            n_val -= 1
        else:
            n_val = 1
            n_test = 1
    n_train = num_users - (n_val + n_test)
    if n_train < 1:
        n_train = 1

    train_users = set(shuffled_users[:n_train])
    val_users = set(shuffled_users[n_train : n_train + n_val])
    test_users = set(shuffled_users[n_train + n_val :])

    # Enforce strict disjointness assertion
    assert not (train_users & val_users), "Data leakage: train and val share users!"
    assert not (train_users & test_users), "Data leakage: train and test share users!"
    assert not (val_users & test_users), "Data leakage: val and test share users!"

    user_splits: dict[uuid.UUID, str] = {}
    for u in train_users:
        user_splits[u] = "train"
    for u in val_users:
        user_splits[u] = "val"
    for u in test_users:
        user_splits[u] = "test"

    session_splits: dict[uuid.UUID, str] = {}
    for sid, s in sessions.items():
        u_split = user_splits[s.user_id]
        session_splits[sid] = u_split

    user_counts = {
        "train": len(train_users),
        "val": len(val_users),
        "test": len(test_users),
    }
    session_counts = {
        "train": sum(1 for s in session_splits.values() if s == "train"),
        "val": sum(1 for s in session_splits.values() if s == "val"),
        "test": sum(1 for s in session_splits.values() if s == "test"),
    }

    return SplitAssignment(
        user_splits=user_splits,
        session_splits=session_splits,
        is_split_valid=True,
        warning=None,
        user_counts=user_counts,
        session_counts=session_counts,
    )
