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

export interface LiveTransportContextValue {
  state: LiveTransportState;
  stream: MediaStream | null;
  videoRef: React.RefObject<HTMLVideoElement>;
  metrics: LiveTransportMetrics;
  error: string | null;
  isLive: boolean;
  startLiveSession: () => Promise<void>;
  stopLiveSession: () => void;
  reconnectLiveSession: () => Promise<void>;
  clearError: () => void;
}
