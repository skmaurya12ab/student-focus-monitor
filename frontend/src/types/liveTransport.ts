/**
 * Live Camera and WebSocket Transport Types (Phase 7).
 * Strictly decoupled from detection logic and ML.
 */

export type LiveTransportState =
  | 'idle'
  | 'starting_camera'
  | 'camera_ready'
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'permission_denied'
  | 'camera_unavailable'
  | 'connection_error'
  | 'stopping';

export interface LiveTransportMetrics {
  framesSent: number;
  framesDropped: number;
  bytesSent: number;
  connectedAt: string | null;
  lastAckReceived: {
    framesReceived: number;
    bytesReceived: number;
  } | null;
}

export interface ActiveDetectionItem {
  category: string;
  alert_name: string;
  started_at: number;
  duration_seconds: number;
}

export interface LiveDetectionResult {
  type: 'detection_result';
  session_id: string;
  timestamp: number;
  state: 'calibrating' | 'focused' | 'distracted' | 'away';
  active_detections: ActiveDetectionItem[];
  metrics: {
    focus_score: number;
    focused_seconds: number;
    distracted_seconds: number;
    away_seconds: number;
    distraction_count: number;
  };
  calibration: {
    complete: boolean;
    samples_collected: number;
    required_samples: number;
    baseline: Record<string, any> | null;
  };
}

export interface LiveTransportContextValue {
  state: LiveTransportState;
  stream: MediaStream | null;
  videoRef: React.RefObject<HTMLVideoElement>;
  metrics: LiveTransportMetrics;
  latestDetection: LiveDetectionResult | null;
  error: string | null;
  isLive: boolean;
  startLiveSession: () => Promise<void>;
  stopLiveSession: () => void;
  reconnectLiveSession: () => Promise<void>;
  clearError: () => void;
}
