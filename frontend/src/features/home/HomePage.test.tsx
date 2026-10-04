import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderToString } from 'react-dom/server';
import { HomePage } from './HomePage';
import { mockHomeData } from '../../data/mock/homeMock';
import { LiveDetectionResult, LiveTransportState } from '../../types/liveTransport';
import { StudySession } from '../../types/session';

function createMockSession(overrides: Partial<StudySession> = {}): StudySession {
  return {
    id: 'sess-default',
    userId: 'u1',
    status: 'active',
    startedAt: new Date(Date.now() - 60000).toISOString(),
    endedAt: null,
    totalDurationSeconds: 60,
    focusedSeconds: 50,
    distractedSeconds: 10,
    awaySeconds: 0,
    focusScore: 83.33,
    distractionCount: 1,
    detectorVersion: 'v1.0.0',
    featureSchemaVersion: 'v1.0.0',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    ...overrides,
  };
}

// Mock contexts
const mockSessionState = {
  activeSession: null as StudySession | null,
  lastCompletedSession: null as StudySession | null,
  isStarting: false,
  isStopping: false,
  sessionError: null as string | null,
  elapsedSeconds: 0,
  isBackendUnavailable: false,
  startSession: vi.fn(),
  stopSession: vi.fn(),
  clearSessionError: vi.fn(),
  refreshActiveSession: vi.fn(),
};

const mockAuthState = {
  isAuthenticated: true,
  user: { id: 'u1', email: 'student@example.com', displayName: 'Saurabh Kumar' },
};

const mockLiveState = {
  state: 'idle' as LiveTransportState,
  stream: null,
  videoRef: { current: null },
  metrics: { framesSent: 0, framesDropped: 0, bytesSent: 0, connectedAt: null, lastAckReceived: null },
  latestDetection: null as LiveDetectionResult | null,
  error: null as string | null,
  isLive: false,
  startLiveSession: vi.fn(),
  stopLiveSession: vi.fn(),
  reconnectLiveSession: vi.fn(),
  clearError: vi.fn(),
};

vi.mock('../../context/SessionContext', () => ({
  useSession: () => mockSessionState,
}));

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => mockAuthState,
}));

vi.mock('../../context/LiveTransportContext', () => ({
  useLiveTransport: () => mockLiveState,
}));

describe('HomePage Component (Phase 9 Live Dashboard Behavior & Integrity)', () => {
  beforeEach(() => {
    mockSessionState.activeSession = null;
    mockSessionState.lastCompletedSession = null;
    mockSessionState.elapsedSeconds = 0;
    mockLiveState.state = 'idle';
    mockLiveState.isLive = false;
    mockLiveState.latestDetection = null;
    mockLiveState.error = null;
    vi.clearAllMocks();
  });

  describe('Section 25 / 32.G — Mock Data Regression Protection', () => {
    it('NEVER restores static Figma sample metrics as live defaults when no active session', () => {
      const html = renderToString(<HomePage data={mockHomeData} />);

      // The old Figma sample metrics that previously leaked into runtime
      expect(html).not.toContain('01:42:18');
      expect(html).not.toContain('00:18:34');
      expect(html).not.toContain('00:04:12');
      expect(html).not.toContain('3h 24m');
      // Verify empty or zero formatted defaults are truthful
      expect(html).toContain('00:00:00');
      expect(html).toContain('0m');
      expect(html).toContain('--');
    });

    it('NEVER restores static Figma sample metrics during an active 1-minute session', () => {
      mockSessionState.activeSession = createMockSession({
        id: 'sess-active-1',
        totalDurationSeconds: 60,
        focusedSeconds: 50,
        distractedSeconds: 10,
        awaySeconds: 0,
        focusScore: 83.33,
        distractionCount: 1,
      });
      mockSessionState.elapsedSeconds = 60;

      const html = renderToString(<HomePage data={mockHomeData} />);

      // Static Figma numbers must NOT leak
      expect(html).not.toContain('01:42:18');
      expect(html).not.toContain('00:18:34');
      expect(html).not.toContain('00:04:12');
      expect(html).not.toContain('3h 24m');
      expect(html).not.toContain('78%');

      // Real values from active session
      expect(html).toContain('00:00:50'); // focused
      expect(html).toContain('00:00:10'); // distracted
      expect(html).toContain('1m'); // study time
      expect(html).toContain('83%'); // focus score
      expect(html).toContain('1'); // distraction count
    });
  });

  describe('Live Monitoring State & Badge Truthfulness', () => {
    it('displays STANDBY when idle', () => {
      mockLiveState.state = 'idle';
      mockLiveState.isLive = false;
      const html = renderToString(<HomePage data={mockHomeData} />);
      expect(html).toContain('STANDBY');
      expect(html).toContain('is-idle');
    });

    it('displays STARTING CAMERA when camera acquisition begins', () => {
      mockLiveState.state = 'starting_camera';
      mockLiveState.isLive = false;
      const html = renderToString(<HomePage data={mockHomeData} />);
      expect(html).toContain('STARTING CAMERA');
      expect(html).toContain('is-starting_camera');
    });

    it('displays CONNECTING while WebSocket connects', () => {
      mockLiveState.state = 'connecting';
      mockLiveState.isLive = false;
      const html = renderToString(<HomePage data={mockHomeData} />);
      expect(html).toContain('CONNECTING');
      expect(html).toContain('is-connecting');
    });

    it('displays CALIBRATING when live but calibration in progress', () => {
      mockSessionState.activeSession = createMockSession({
        id: 'sess-1',
        totalDurationSeconds: 60,
        focusedSeconds: 0,
        distractedSeconds: 0,
        awaySeconds: 0,
        focusScore: 100,
        distractionCount: 0,
      });
      mockLiveState.state = 'connected';
      mockLiveState.isLive = true;
      mockLiveState.latestDetection = {
        type: 'detection_result',
        session_id: 'sess-1',
        timestamp: 100,
        state: 'calibrating',
        active_detections: [],
        metrics: { focus_score: 100, focused_seconds: 0, distracted_seconds: 0, away_seconds: 0, distraction_count: 0 },
        calibration: { complete: false, samples_collected: 10, required_samples: 30, baseline: null },
      };

      const html = renderToString(<HomePage data={mockHomeData} />);
      expect(html).toContain('CALIBRATING');
      expect(html).toContain('is-calibrating');
      expect(html).toContain('Calibrating baseline posture (10/30 samples)');
    });

    it('displays LIVE / FOCUSED when monitoring in healthy focused state', () => {
      mockSessionState.activeSession = createMockSession({
        id: 'sess-1',
        totalDurationSeconds: 60,
        focusedSeconds: 50,
        distractedSeconds: 0,
        awaySeconds: 0,
        focusScore: 95,
        distractionCount: 0,
      });
      mockLiveState.state = 'connected';
      mockLiveState.isLive = true;
      mockLiveState.latestDetection = {
        type: 'detection_result',
        session_id: 'sess-1',
        timestamp: 100,
        state: 'focused',
        active_detections: [],
        metrics: { focus_score: 95, focused_seconds: 120, distracted_seconds: 0, away_seconds: 0, distraction_count: 0 },
        calibration: { complete: true, samples_collected: 30, required_samples: 30, baseline: {} },
      };

      const html = renderToString(<HomePage data={mockHomeData} />);
      expect(html).toContain('LIVE / FOCUSED');
      expect(html).toContain('is-focused');
      expect(html).toContain('Maintaining focus');
    });

    it('displays LIVE / DISTRACTED and alert pills when distraction is reported', () => {
      mockSessionState.activeSession = createMockSession({
        id: 'sess-1',
        totalDurationSeconds: 60,
        focusedSeconds: 45,
        distractedSeconds: 15,
        awaySeconds: 0,
        focusScore: 85,
        distractionCount: 1,
      });
      mockLiveState.state = 'connected';
      mockLiveState.isLive = true;
      mockLiveState.latestDetection = {
        type: 'detection_result',
        session_id: 'sess-1',
        timestamp: 100,
        state: 'distracted',
        active_detections: [
          {
            category: 'looking_away',
            alert_name: 'Looking Away',
            started_at: 85,
            duration_seconds: 15,
          },
        ],
        metrics: { focus_score: 85, focused_seconds: 120, distracted_seconds: 15, away_seconds: 0, distraction_count: 1 },
        calibration: { complete: true, samples_collected: 30, required_samples: 30, baseline: {} },
      };

      const html = renderToString(<HomePage data={mockHomeData} />);
      expect(html).toContain('LIVE / DISTRACTED');
      expect(html).toContain('DISTRACTED');
      expect(html).toContain('Looking Away');
      expect(html).toContain('(15s)');
    });

    it('supports multiple simultaneous active detections without discarding secondary ones', () => {
      mockSessionState.activeSession = createMockSession({
        id: 'sess-1',
        totalDurationSeconds: 60,
        focusedSeconds: 40,
        distractedSeconds: 20,
        awaySeconds: 0,
        focusScore: 75,
        distractionCount: 2,
      });
      mockLiveState.state = 'connected';
      mockLiveState.isLive = true;
      mockLiveState.latestDetection = {
        type: 'detection_result',
        session_id: 'sess-1',
        timestamp: 100,
        state: 'distracted',
        active_detections: [
          {
            category: 'looking_away',
            alert_name: 'Looking Away',
            started_at: 80,
            duration_seconds: 20,
          },
          {
            category: 'phone_use',
            alert_name: 'Phone Use',
            started_at: 92,
            duration_seconds: 8,
          },
        ],
        metrics: { focus_score: 75, focused_seconds: 120, distracted_seconds: 20, away_seconds: 0, distraction_count: 2 },
        calibration: { complete: true, samples_collected: 30, required_samples: 30, baseline: {} },
      };

      const html = renderToString(<HomePage data={mockHomeData} />);
      expect(html).toContain('Looking Away');
      expect(html).toContain('(20s)');
      expect(html).toContain('Phone Use');
      expect(html).toContain('(8s)');
    });

    it('displays LIVE / AWAY when student leaves desk', () => {
      mockSessionState.activeSession = createMockSession({
        id: 'sess-1',
        totalDurationSeconds: 60,
        focusedSeconds: 55,
        distractedSeconds: 0,
        awaySeconds: 5,
        focusScore: 80,
        distractionCount: 1,
      });
      mockLiveState.state = 'connected';
      mockLiveState.isLive = true;
      mockLiveState.latestDetection = {
        type: 'detection_result',
        session_id: 'sess-1',
        timestamp: 100,
        state: 'away',
        active_detections: [
          { category: 'away_from_desk', alert_name: 'Away From Desk', started_at: 95, duration_seconds: 5 },
        ],
        metrics: { focus_score: 80, focused_seconds: 120, distracted_seconds: 20, away_seconds: 5, distraction_count: 1 },
        calibration: { complete: true, samples_collected: 30, required_samples: 30, baseline: {} },
      };

      const html = renderToString(<HomePage data={mockHomeData} />);
      expect(html).toContain('LIVE / AWAY');
      expect(html).toContain('AWAY FROM DESK');
    });

    it('displays LIVE DISCONNECTED when websocket drops', () => {
      mockLiveState.state = 'disconnected';
      mockLiveState.isLive = false;
      const html = renderToString(<HomePage data={mockHomeData} />);
      expect(html).toContain('LIVE DISCONNECTED');
    });

    it('displays CAMERA ERROR when camera access fails or is denied', () => {
      mockLiveState.state = 'permission_denied';
      mockLiveState.isLive = false;
      const html = renderToString(<HomePage data={mockHomeData} />);
      expect(html).toContain('CAMERA ERROR');
      expect(html).toContain('is-error');
    });

    it('displays DETECTOR ERROR when detector fails or encounters connection error', () => {
      mockLiveState.state = 'connection_error';
      mockLiveState.isLive = false;
      const html = renderToString(<HomePage data={mockHomeData} />);
      expect(html).toContain('DETECTOR ERROR');
      expect(html).toContain('is-error');
    });
  });

  describe('Focus Timeline', () => {
    it('shows empty timeline placeholder when no session is active', () => {
      mockSessionState.activeSession = null;
      const html = renderToString(<HomePage data={mockHomeData} />);
      expect(html).toContain('focus-timeline-empty-track');
      expect(html).toContain('No active session timeline yet');
    });

    it('shows dynamic timeline segments during an active study session', () => {
      mockSessionState.activeSession = createMockSession({
        id: 'sess-tl-1',
        totalDurationSeconds: 300,
        focusedSeconds: 240,
        distractedSeconds: 60,
        awaySeconds: 0,
        focusScore: 80,
        distractionCount: 1,
      });

      const html = renderToString(<HomePage data={mockHomeData} />);
      expect(html).toContain('focus-timeline-segments-track');
      expect(html).not.toContain('No active session timeline yet');
    });
  });

  describe('Persistent Distraction Banner (Phase 9 Correction)', () => {
    it('does NOT display banner when user is focused or idle', () => {
      mockSessionState.activeSession = createMockSession();
      mockLiveState.isLive = true;
      mockLiveState.latestDetection = {
        type: 'detection_result',
        session_id: 's1',
        timestamp: 100,
        state: 'focused',
        active_detections: [],
        metrics: { focus_score: 95, focused_seconds: 100, distracted_seconds: 0, away_seconds: 0, distraction_count: 0 },
        calibration: { complete: true, samples_collected: 30, required_samples: 30, baseline: {} },
      };

      const html = renderToString(<HomePage data={mockHomeData} />);
      expect(html).not.toContain('persistent-distraction-banner');
      expect(html).not.toContain('YOU ARE DISTRACTED');
    });

    it('displays prominent distraction banner when distraction begins', () => {
      mockSessionState.activeSession = createMockSession();
      mockLiveState.isLive = true;
      mockLiveState.latestDetection = {
        type: 'detection_result',
        session_id: 's1',
        timestamp: 100,
        state: 'distracted',
        active_detections: [
          { category: 'phone_use', alert_name: 'Phone Use', started_at: 94, duration_seconds: 6 },
        ],
        metrics: { focus_score: 80, focused_seconds: 90, distracted_seconds: 6, away_seconds: 0, distraction_count: 1 },
        calibration: { complete: true, samples_collected: 30, required_samples: 30, baseline: {} },
      };

      const html = renderToString(<HomePage data={mockHomeData} />);
      expect(html).toContain('persistent-distraction-banner');
      expect(html).toContain('YOU ARE DISTRACTED');
      expect(html).toContain('Phone Use');
      expect(html).toContain('Active for 6s');
    });

    it('displays single consolidated banner when multiple simultaneous distractions occur', () => {
      mockSessionState.activeSession = createMockSession();
      mockLiveState.isLive = true;
      mockLiveState.latestDetection = {
        type: 'detection_result',
        session_id: 's1',
        timestamp: 100,
        state: 'distracted',
        active_detections: [
          { category: 'phone_use', alert_name: 'Phone Use', started_at: 92, duration_seconds: 8 },
          { category: 'looking_away', alert_name: 'Looking Away', started_at: 90, duration_seconds: 10 },
        ],
        metrics: { focus_score: 75, focused_seconds: 80, distracted_seconds: 10, away_seconds: 0, distraction_count: 2 },
        calibration: { complete: true, samples_collected: 30, required_samples: 30, baseline: {} },
      };

      const html = renderToString(<HomePage data={mockHomeData} />);
      expect(html).toContain('persistent-distraction-banner');
      expect(html).toContain('YOU ARE DISTRACTED');
      expect(html).toContain('Phone Use • Looking Away');
      expect(html).toContain('Active for 10s');
    });

    it('banner does NOT appear during error states or disconnects', () => {
      mockSessionState.activeSession = createMockSession();
      mockLiveState.isLive = false;
      mockLiveState.state = 'permission_denied';
      mockLiveState.latestDetection = null;

      const html = renderToString(<HomePage data={mockHomeData} />);
      expect(html).not.toContain('persistent-distraction-banner');
      expect(html).toContain('CAMERA ERROR');
    });
  });
});
