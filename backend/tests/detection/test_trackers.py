"""Tests for condition persistence tracking and alert activation timing."""

import pytest
from app.detection.config import (
    ALERT_AWAY_FROM_DESK,
    ALERT_LOOKING_AWAY,
    ALERT_PHONE_USE,
    ALERT_YAWNING,
    DetectorConfig,
)
from app.detection.trackers import MultiCategoryTracker, PersistenceTracker


def test_tracker_starts_inactive():
    tracker = PersistenceTracker(delay=20.0)
    assert not tracker.is_active
    assert tracker.condition_started_at is None
    assert tracker.alert_started_at is None


def test_tracker_remains_inactive_before_threshold():
    tracker = PersistenceTracker(delay=20.0)
    t0 = 1000.0

    # First trigger at t=0
    res = tracker.update(condition_is_true=True, now=t0)
    assert not res.active
    assert not res.just_started
    assert not res.just_ended
    assert res.duration_sec is None

    # Intermediate time steps before 20s
    res = tracker.update(condition_is_true=True, now=t0 + 10.0)
    assert not res.active
    assert not res.just_started

    # 19.9s: just below 20s threshold
    res = tracker.update(condition_is_true=True, now=t0 + 19.9)
    assert not res.active
    assert not res.just_started
    assert not tracker.is_active


def test_tracker_exact_threshold_boundary():
    tracker = PersistenceTracker(delay=20.0)
    t0 = 1000.0

    tracker.update(condition_is_true=True, now=t0)
    # Exactly at 20.0s threshold
    res = tracker.update(condition_is_true=True, now=t0 + 20.0)
    assert res.active
    assert res.just_started
    assert not res.just_ended
    assert res.duration_sec == pytest.approx(0.0)
    assert tracker.is_active


def test_tracker_continues_active_after_threshold():
    tracker = PersistenceTracker(delay=20.0)
    t0 = 1000.0

    tracker.update(condition_is_true=True, now=t0)
    tracker.update(condition_is_true=True, now=t0 + 20.0)

    # At 25.0s (5s after alert started)
    res = tracker.update(condition_is_true=True, now=t0 + 25.0)
    assert res.active
    assert not res.just_started  # Only just_started on activation tick
    assert not res.just_ended
    assert res.duration_sec == pytest.approx(5.0)


def test_tracker_clears_and_ends_when_condition_stops():
    tracker = PersistenceTracker(delay=20.0)
    t0 = 1000.0

    tracker.update(condition_is_true=True, now=t0)
    tracker.update(condition_is_true=True, now=t0 + 20.0)
    tracker.update(condition_is_true=True, now=t0 + 25.0)

    # Condition becomes False at 30.0s
    res = tracker.update(condition_is_true=False, now=t0 + 30.0)
    assert not res.active
    assert not res.just_started
    assert res.just_ended
    assert res.duration_sec == pytest.approx(10.0)  # Alert ran from t0+20 to t0+30
    assert not tracker.is_active
    assert tracker.condition_started_at is None
    assert tracker.alert_started_at is None


def test_tracker_transient_flicker_does_not_trigger_just_ended():
    tracker = PersistenceTracker(delay=20.0)
    t0 = 1000.0

    # Condition active for only 5s (never reached 20s)
    tracker.update(condition_is_true=True, now=t0)
    tracker.update(condition_is_true=True, now=t0 + 5.0)

    # Clears before threshold
    res = tracker.update(condition_is_true=False, now=t0 + 6.0)
    assert not res.active
    assert not res.just_started
    assert not res.just_ended  # Was never an alert, so no alert ended
    assert res.duration_sec is None


def test_tracker_manual_reset():
    tracker = PersistenceTracker(delay=20.0)
    t0 = 1000.0
    tracker.update(condition_is_true=True, now=t0)
    tracker.update(condition_is_true=True, now=t0 + 20.0)
    assert tracker.is_active

    tracker.reset()
    assert not tracker.is_active
    assert tracker.condition_started_at is None
    assert tracker.alert_started_at is None


def test_tracker_reactivation():
    tracker = PersistenceTracker(delay=5.0)
    t0 = 100.0

    # First cycle
    tracker.update(True, t0)
    res1 = tracker.update(True, t0 + 5.0)
    assert res1.just_started
    tracker.update(False, t0 + 10.0)

    # Second cycle at t=200.0
    tracker.update(True, 200.0)
    res2 = tracker.update(True, 204.9)
    assert not res2.active

    res3 = tracker.update(True, 205.0)
    assert res3.active
    assert res3.just_started


def test_multi_category_tracker_independent_and_simultaneous():
    config = DetectorConfig(
        alert_delays_sec={
            ALERT_YAWNING: 2.0,
            ALERT_LOOKING_AWAY: 10.0,
            ALERT_PHONE_USE: 15.0,
            ALERT_AWAY_FROM_DESK: 20.0,
        }
    )
    multi = MultiCategoryTracker(config)
    t0 = 1000.0

    # At t0, Yawning and Looking Away both become True
    conditions = {
        ALERT_YAWNING: True,
        ALERT_LOOKING_AWAY: True,
        ALERT_PHONE_USE: False,
    }
    results, active = multi.update(conditions, now=t0)
    assert active == []

    # At t0 + 2.0s: Yawning delay (2s) reached, Looking Away (10s) not reached
    results, active = multi.update(conditions, now=t0 + 2.0)
    assert active == [ALERT_YAWNING]
    assert results[ALERT_YAWNING].just_started
    assert not results[ALERT_LOOKING_AWAY].active

    # At t0 + 10.0s: Looking Away also triggers -> simultaneous alerts
    results, active = multi.update(conditions, now=t0 + 10.0)
    assert set(active) == {ALERT_YAWNING, ALERT_LOOKING_AWAY}
    assert results[ALERT_LOOKING_AWAY].just_started

    # Clear Yawning, keep Looking Away
    conditions[ALERT_YAWNING] = False
    results, active = multi.update(conditions, now=t0 + 12.0)
    assert active == [ALERT_LOOKING_AWAY]
    assert results[ALERT_YAWNING].just_ended
    assert results[ALERT_LOOKING_AWAY].active
