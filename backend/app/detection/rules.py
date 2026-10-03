"""Pure rule evaluation module defining the 6 core distraction detection conditions."""

from __future__ import annotations

from typing import Mapping

from app.detection.config import (
    ALERT_AWAY_FROM_DESK,
    ALERT_DROWSY,
    ALERT_LEANING_BACK,
    ALERT_LOOKING_AWAY,
    ALERT_PHONE_USE,
    ALERT_YAWNING,
    CATEGORY_AWAY_FROM_DESK,
    CATEGORY_DROWSY,
    CATEGORY_LEANING_BACK,
    CATEGORY_LOOKING_AWAY,
    CATEGORY_PHONE_USE,
    CATEGORY_YAWNING,
    DetectorConfig,
)
from app.detection.features import FeatureSnapshot


def is_looking_away(features: FeatureSnapshot, config: DetectorConfig) -> bool:
    """
    Looking Away condition:
    Evaluates whether the student's face is present and their head yaw deviation
    from their calibrated baseline exceeds the configured threshold.
    """
    if not features.face_present:
        return False
    if features.head_yaw_from_baseline is None:
        return False
    return abs(features.head_yaw_from_baseline) > config.yaw_threshold_deg


def is_phone_use(features: FeatureSnapshot, config: DetectorConfig) -> bool:
    """
    Phone Use condition:
    Evaluates whether the student's face is present and a detected hand is within
    the threshold proximity distance to either cheek.
    """
    if not features.face_present:
        return False
    if features.hand_cheek_distance is None:
        return False
    return features.hand_cheek_distance < config.hand_near_cheek_dist


def is_yawning(features: FeatureSnapshot, config: DetectorConfig) -> bool:
    """
    Yawning condition:
    Evaluates whether the student's face is present and their Mouth Aspect Ratio (MAR)
    exceeds the configured threshold.
    """
    if not features.face_present:
        return False
    if features.mar is None:
        return False
    return features.mar > config.mar_threshold


def is_drowsy(features: FeatureSnapshot, config: DetectorConfig) -> bool:
    """
    Drowsy / Eyes Closed condition:
    Evaluates whether the student's face is present and their Eye Aspect Ratio (EAR)
    falls below the configured threshold.
    """
    if not features.face_present:
        return False
    if features.ear is None:
        return False
    return features.ear < config.ear_threshold


def is_leaning_back(features: FeatureSnapshot, config: DetectorConfig) -> bool:
    """
    Leaning Back condition:
    Evaluates whether the student's pose is present and their shoulder depth z-deviation
    from their calibrated baseline exceeds the configured positive threshold.
    """
    if not features.pose_present:
        return False
    if features.shoulder_z_delta is None:
        return False
    return features.shoulder_z_delta > config.lean_back_z_delta


def is_away_from_desk(features: FeatureSnapshot, _config: DetectorConfig) -> bool:
    """
    Away From Desk condition:
    Evaluates whether neither face nor pose landmarks are detected in the frame.
    """
    return not features.face_present and not features.pose_present


def evaluate_rules(
    features: FeatureSnapshot,
    config: DetectorConfig,
) -> dict[str, bool]:
    """
    Evaluate all 6 detection rules against a feature snapshot.
    Returns a dictionary keyed by canonical human-readable alert names (v4 compatible).
    """
    return {
        ALERT_LOOKING_AWAY: is_looking_away(features, config),
        ALERT_PHONE_USE: is_phone_use(features, config),
        ALERT_YAWNING: is_yawning(features, config),
        ALERT_DROWSY: is_drowsy(features, config),
        ALERT_LEANING_BACK: is_leaning_back(features, config),
        ALERT_AWAY_FROM_DESK: is_away_from_desk(features, config),
    }


def evaluate_rules_by_category(
    features: FeatureSnapshot,
    config: DetectorConfig,
) -> dict[str, bool]:
    """
    Evaluate all 6 detection rules keyed by stable machine-readable category identifiers.
    """
    return {
        CATEGORY_LOOKING_AWAY: is_looking_away(features, config),
        CATEGORY_PHONE_USE: is_phone_use(features, config),
        CATEGORY_YAWNING: is_yawning(features, config),
        CATEGORY_DROWSY: is_drowsy(features, config),
        CATEGORY_LEANING_BACK: is_leaning_back(features, config),
        CATEGORY_AWAY_FROM_DESK: is_away_from_desk(features, config),
    }
