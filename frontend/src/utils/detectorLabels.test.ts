import { describe, it, expect } from 'vitest';
import {
  CANONICAL_DETECTOR_CATEGORIES,
  getDetectorCategoryLabel,
  formatAlertDuration,
  resolveLiveBadgeStatus,
} from './detectorLabels';
import { LiveDetectionResult } from '../types/liveTransport';

describe('detectorLabels (Phase 9 Canonical Categories and Truthful Status)', () => {
  it('preserves all six canonical detector categories', () => {
    expect(CANONICAL_DETECTOR_CATEGORIES).toEqual([
      'looking_away',
      'phone_use',
      'yawning',
      'drowsy',
      'leaning_back',
      'away_from_desk',
    ]);
  });

  it('provides correct human-readable labels for all six categories', () => {
    expect(getDetectorCategoryLabel('looking_away')).toBe('Looking Away');
    expect(getDetectorCategoryLabel('phone_use')).toBe('Phone Use');
    expect(getDetectorCategoryLabel('yawning')).toBe('Yawning');
    expect(getDetectorCategoryLabel('drowsy')).toBe('Drowsiness / Eyes Closed');
    expect(getDetectorCategoryLabel('leaning_back')).toBe('Leaning Back');
    expect(getDetectorCategoryLabel('away_from_desk')).toBe('Away From Desk');
  });

  it('formats alert durations correctly', () => {
    expect(formatAlertDuration(0)).toBe('0s');
    expect(formatAlertDuration(14.8)).toBe('14s');
    expect(formatAlertDuration(60)).toBe('1m 0s');
    expect(formatAlertDuration(125)).toBe('2m 5s');
  });

  describe('resolveLiveBadgeStatus', () => {
    it('returns STANDBY when idle and not live', () => {
      const status = resolveLiveBadgeStatus(false, 'idle', null);
      expect(status.text).toBe('STANDBY');
      expect(status.isPulsing).toBe(false);
      expect(status.stateKey).toBe('standby');
    });

    it('returns STARTING CAMERA when camera request starts', () => {
      const status = resolveLiveBadgeStatus(false, 'starting_camera', null);
      expect(status.text).toBe('STARTING CAMERA');
      expect(status.isPulsing).toBe(true);
      expect(status.stateKey).toBe('starting_camera');
    });

    it('returns CONNECTING while WebSocket connects', () => {
      const status = resolveLiveBadgeStatus(false, 'connecting', null);
      expect(status.text).toBe('CONNECTING');
      expect(status.isPulsing).toBe(true);
      expect(status.stateKey).toBe('connecting');
    });

    it('returns CAMERA ERROR on permission denied or camera unavailable', () => {
      const denied = resolveLiveBadgeStatus(false, 'permission_denied', null);
      expect(denied.text).toBe('CAMERA ERROR');
      expect(denied.stateKey).toBe('camera_error');

      const unavailable = resolveLiveBadgeStatus(false, 'camera_unavailable', null);
      expect(unavailable.text).toBe('CAMERA ERROR');
      expect(unavailable.stateKey).toBe('camera_error');
    });

    it('returns DETECTOR ERROR on connection_error', () => {
      const err = resolveLiveBadgeStatus(false, 'connection_error', null);
      expect(err.text).toBe('DETECTOR ERROR');
      expect(err.stateKey).toBe('detector_error');
    });

    it('returns LIVE DISCONNECTED when disconnected', () => {
      const disco = resolveLiveBadgeStatus(false, 'disconnected', null);
      expect(disco.text).toBe('LIVE DISCONNECTED');
      expect(disco.stateKey).toBe('disconnected');
    });

    it('returns CALIBRATING when live but detection is null or calibrating', () => {
      const noDetection = resolveLiveBadgeStatus(true, 'connected', null);
      expect(noDetection.text).toBe('CALIBRATING');
      expect(noDetection.stateKey).toBe('calibrating');

      const calibratingPayload: LiveDetectionResult = {
        type: 'detection_result',
        session_id: 'test-session',
        timestamp: 100,
        state: 'calibrating',
        active_detections: [],
        metrics: {
          focus_score: 100,
          focused_seconds: 0,
          distracted_seconds: 0,
          away_seconds: 0,
          distraction_count: 0,
        },
        calibration: {
          complete: false,
          samples_collected: 5,
          required_samples: 30,
          baseline: null,
        },
      };

      const calib = resolveLiveBadgeStatus(true, 'connected', calibratingPayload);
      expect(calib.text).toBe('CALIBRATING');
      expect(calib.stateKey).toBe('calibrating');
    });

    it('returns LIVE / FOCUSED when monitoring in focused state', () => {
      const focusedPayload: LiveDetectionResult = {
        type: 'detection_result',
        session_id: 'test-session',
        timestamp: 100,
        state: 'focused',
        active_detections: [],
        metrics: {
          focus_score: 95,
          focused_seconds: 50,
          distracted_seconds: 0,
          away_seconds: 0,
          distraction_count: 0,
        },
        calibration: {
          complete: true,
          samples_collected: 30,
          required_samples: 30,
          baseline: {},
        },
      };

      const focused = resolveLiveBadgeStatus(true, 'connected', focusedPayload);
      expect(focused.text).toBe('LIVE / FOCUSED');
      expect(focused.stateKey).toBe('focused');
      expect(focused.isPulsing).toBe(true);
    });

    it('returns LIVE / DISTRACTED when monitoring in distracted state', () => {
      const distractedPayload: LiveDetectionResult = {
        type: 'detection_result',
        session_id: 'test-session',
        timestamp: 100,
        state: 'distracted',
        active_detections: [
          {
            category: 'looking_away',
            alert_name: 'Looking Away',
            started_at: 80,
            duration_seconds: 20,
          },
        ],
        metrics: {
          focus_score: 80,
          focused_seconds: 50,
          distracted_seconds: 20,
          away_seconds: 0,
          distraction_count: 1,
        },
        calibration: {
          complete: true,
          samples_collected: 30,
          required_samples: 30,
          baseline: {},
        },
      };

      const distracted = resolveLiveBadgeStatus(true, 'connected', distractedPayload);
      expect(distracted.text).toBe('LIVE / DISTRACTED');
      expect(distracted.stateKey).toBe('distracted');
      expect(distracted.isPulsing).toBe(true);
    });

    it('returns LIVE / AWAY when monitoring in away state', () => {
      const awayPayload: LiveDetectionResult = {
        type: 'detection_result',
        session_id: 'test-session',
        timestamp: 100,
        state: 'away',
        active_detections: [
          {
            category: 'away_from_desk',
            alert_name: 'Away From Desk',
            started_at: 90,
            duration_seconds: 10,
          },
        ],
        metrics: {
          focus_score: 75,
          focused_seconds: 50,
          distracted_seconds: 20,
          away_seconds: 10,
          distraction_count: 1,
        },
        calibration: {
          complete: true,
          samples_collected: 30,
          required_samples: 30,
          baseline: {},
        },
      };

      const away = resolveLiveBadgeStatus(true, 'connected', awayPayload);
      expect(away.text).toBe('LIVE / AWAY');
      expect(away.stateKey).toBe('away');
    });

    it('returns DETECTOR ERROR if detection payload has detector_error state', () => {
      const errorPayload: any = {
        type: 'detection_result',
        session_id: 'test-session',
        timestamp: 100,
        state: 'detector_error',
        active_detections: [],
        metrics: {
          focus_score: 0,
          focused_seconds: 0,
          distracted_seconds: 0,
          away_seconds: 0,
          distraction_count: 0,
        },
        calibration: { complete: false, samples_collected: 0, required_samples: 30, baseline: null },
      };

      const errStatus = resolveLiveBadgeStatus(true, 'connected', errorPayload);
      expect(errStatus.text).toBe('DETECTOR ERROR');
      expect(errStatus.stateKey).toBe('detector_error');
    });
  });
});
