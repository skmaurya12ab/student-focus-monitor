"""Tests for personal calibration buffer and user-specific baseline calculations."""

import pytest
from app.detection.calibration import CalibrationBaseline, CalibrationBuffer


def test_calibration_buffer_starts_incomplete():
    cal = CalibrationBuffer(required_seconds=10.0, min_samples=30)
    assert not cal.complete
    assert cal.baseline.shoulder_z is None
    assert cal.baseline.head_yaw is None


def test_calibration_fails_on_insufficient_samples():
    cal = CalibrationBuffer(required_seconds=5.0, min_samples=30)
    t0 = 1000.0

    # Only 10 samples over 6 seconds
    for i in range(10):
        done = cal.add(
            now=t0 + (i * 0.6),
            shoulder_z=-0.04,
            head_yaw=1.5,
            head_pitch=0.0,
            head_roll=0.0,
        )

    assert not done
    assert not cal.complete
    assert cal.baseline.shoulder_z is None


def test_calibration_fails_on_insufficient_time():
    cal = CalibrationBuffer(required_seconds=10.0, min_samples=20)
    t0 = 1000.0

    # 40 samples but in only 2 seconds
    for i in range(40):
        done = cal.add(
            now=t0 + (i * 0.05),
            shoulder_z=-0.04,
            head_yaw=1.5,
            head_pitch=0.0,
            head_roll=0.0,
        )

    assert not done
    assert not cal.complete


def test_calibration_succeeds_when_criteria_met():
    cal = CalibrationBuffer(required_seconds=5.0, min_samples=20)
    t0 = 1000.0

    # Feed 30 samples spanning 6 seconds with known values
    shoulder_samples = [-0.05, -0.04, -0.04, -0.03, -0.04] * 6
    yaw_samples = [2.0, 2.2, 1.9, 2.1, 2.0] * 6

    for i in range(30):
        done = cal.add(
            now=t0 + (i * 0.2),
            shoulder_z=shoulder_samples[i],
            head_yaw=yaw_samples[i],
            head_pitch=10.0,
            head_roll=-1.0,
        )

    assert done
    assert cal.complete
    assert cal.baseline.shoulder_z == pytest.approx(-0.04)
    assert cal.baseline.head_yaw == pytest.approx(2.0)
    assert cal.baseline.head_pitch == pytest.approx(10.0)
    assert cal.baseline.head_roll == pytest.approx(-1.0)


def test_user_specific_baselines_student_a_and_b():
    """
    Required conceptual test:
    Student A baseline shoulder_z = -0.03
    Student B baseline shoulder_z = +0.08
    Apply equivalent relative movement (+0.18 lean-back delta).
    Both must be interpreted according to their OWN baseline!
    """
    cal_a = CalibrationBuffer(required_seconds=1.0, min_samples=5)
    cal_b = CalibrationBuffer(required_seconds=1.0, min_samples=5)
    t0 = 100.0

    # Calibrate Student A around shoulder_z = -0.03
    for i in range(10):
        cal_a.add(now=t0 + i * 0.2, shoulder_z=-0.03, head_yaw=0.0, head_pitch=0.0, head_roll=0.0)

    # Calibrate Student B around shoulder_z = +0.08
    for i in range(10):
        cal_b.add(now=t0 + i * 0.2, shoulder_z=+0.08, head_yaw=5.0, head_pitch=0.0, head_roll=0.0)

    assert cal_a.complete
    assert cal_b.complete
    assert cal_a.baseline.shoulder_z == pytest.approx(-0.03)
    assert cal_b.baseline.shoulder_z == pytest.approx(+0.08)

    # Now both students lean back by exactly +0.18 relative to their respective posture:
    # Student A raw shoulder_z = -0.03 + 0.18 = +0.15
    # Student B raw shoulder_z = +0.08 + 0.18 = +0.26
    raw_shoulder_a = -0.03 + 0.18
    raw_shoulder_b = +0.08 + 0.18

    _, _, _, delta_a = cal_a.compute_relative_deltas(None, None, None, raw_shoulder_a)
    _, _, _, delta_b = cal_b.compute_relative_deltas(None, None, None, raw_shoulder_b)

    # Both must report the identical relative displacement of +0.18!
    assert delta_a == pytest.approx(0.18)
    assert delta_b == pytest.approx(0.18)

    # Without user calibration, raw +0.15 would mean something completely different for Student B.


def test_calibration_reset():
    cal = CalibrationBuffer(required_seconds=1.0, min_samples=5)
    t0 = 100.0
    for i in range(10):
        cal.add(now=t0 + i * 0.2, shoulder_z=-0.03, head_yaw=0.0, head_pitch=0.0, head_roll=0.0)
    assert cal.complete

    cal.reset()
    assert not cal.complete
    assert cal.started_at is None
    assert len(cal.shoulder_z) == 0
    assert cal.baseline.shoulder_z is None
