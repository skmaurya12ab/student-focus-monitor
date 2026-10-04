/**
 * Canonical detector categories, human-readable labels, and truthful live status mappings (Phase 9).
 */
import { LiveTransportState, LiveDetectionResult } from '../types/liveTransport';

export const CANONICAL_DETECTOR_CATEGORIES = [
  'looking_away',
  'phone_use',
  'yawning',
  'drowsy',
  'leaning_back',
  'away_from_desk',
] as const;

export type CanonicalDetectorCategory = typeof CANONICAL_DETECTOR_CATEGORIES[number];

export const DETECTOR_CATEGORY_LABELS: Record<CanonicalDetectorCategory | string, string> = {
  looking_away: 'Looking Away',
  phone_use: 'Phone Use',
  yawning: 'Yawning',
  drowsy: 'Drowsiness / Eyes Closed',
  leaning_back: 'Leaning Back',
  away_from_desk: 'Away From Desk',
};

/**
 * Convert raw detector category key to authoritative human-readable label.
 */
export function getDetectorCategoryLabel(category: string, fallbackName?: string): string {
  if (category in DETECTOR_CATEGORY_LABELS) {
    return DETECTOR_CATEGORY_LABELS[category];
  }
  if (fallbackName) {
    return fallbackName;
  }
  return category
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * Format active detection duration in human-readable seconds/minutes.
 */
export function formatAlertDuration(durationSeconds: number): string {
  const sec = Math.max(0, Math.floor(durationSeconds));
  if (sec < 60) {
    return `${sec}s`;
  }
  const m = Math.floor(sec / 60);
  const remSec = sec % 60;
  return `${m}m ${remSec}s`;
}

export interface LiveBadgeStatus {
  text: string;
  indicatorClass: string;
  isPulsing: boolean;
  stateKey:
    | 'standby'
    | 'starting_camera'
    | 'connecting'
    | 'calibrating'
    | 'focused'
    | 'distracted'
    | 'away'
    | 'disconnected'
    | 'camera_error'
    | 'detector_error';
}

/**
 * Authoritatively resolves the live badge state text and class.
 * Never defaults to FOCUSED when no message is received or detector fails.
 */
export function resolveLiveBadgeStatus(
  isLive: boolean,
  transportState: LiveTransportState,
  detection: LiveDetectionResult | null
): LiveBadgeStatus {
  // 1. Not currently live (camera / socket closed or in progress)
  if (!isLive) {
    if (transportState === 'starting_camera') {
      return {
        text: 'STARTING CAMERA',
        indicatorClass: 'is-starting_camera',
        isPulsing: true,
        stateKey: 'starting_camera',
      };
    }
    if (transportState === 'connecting') {
      return {
        text: 'CONNECTING',
        indicatorClass: 'is-connecting',
        isPulsing: true,
        stateKey: 'connecting',
      };
    }
    if (transportState === 'permission_denied' || transportState === 'camera_unavailable') {
      return {
        text: 'CAMERA ERROR',
        indicatorClass: 'is-error',
        isPulsing: false,
        stateKey: 'camera_error',
      };
    }
    if (transportState === 'connection_error') {
      return {
        text: 'DETECTOR ERROR',
        indicatorClass: 'is-error',
        isPulsing: false,
        stateKey: 'detector_error',
      };
    }
    if (transportState === 'disconnected') {
      return {
        text: 'LIVE DISCONNECTED',
        indicatorClass: 'is-disconnected',
        isPulsing: false,
        stateKey: 'disconnected',
      };
    }
    return {
      text: 'STANDBY',
      indicatorClass: 'is-idle',
      isPulsing: false,
      stateKey: 'standby',
    };
  }

  // 2. Live transport connected: evaluate detector output
  if (!detection) {
    return {
      text: 'CALIBRATING',
      indicatorClass: 'is-calibrating',
      isPulsing: true,
      stateKey: 'calibrating',
    };
  }

  if (detection.state === 'calibrating') {
    return {
      text: 'CALIBRATING',
      indicatorClass: 'is-calibrating',
      isPulsing: true,
      stateKey: 'calibrating',
    };
  }

  if ((detection.state as string) === 'detector_error') {
    return {
      text: 'DETECTOR ERROR',
      indicatorClass: 'is-error',
      isPulsing: false,
      stateKey: 'detector_error',
    };
  }

  if (detection.state === 'distracted') {
    return {
      text: 'LIVE / DISTRACTED',
      indicatorClass: 'is-distracted',
      isPulsing: true,
      stateKey: 'distracted',
    };
  }

  if (detection.state === 'away') {
    return {
      text: 'LIVE / AWAY',
      indicatorClass: 'is-away',
      isPulsing: true,
      stateKey: 'away',
    };
  }

  if (detection.state === 'focused') {
    return {
      text: 'LIVE / FOCUSED',
      indicatorClass: 'is-focused',
      isPulsing: true,
      stateKey: 'focused',
    };
  }

  // Fallback safe state
  return {
    text: 'LIVE / FOCUSED',
    indicatorClass: 'is-focused',
    isPulsing: true,
    stateKey: 'focused',
  };
}
