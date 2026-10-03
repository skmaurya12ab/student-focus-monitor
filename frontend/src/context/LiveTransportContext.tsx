/**
 * Live Transport Context (Phase 7).
 * Coordinates camera hardware acquisition, video preview attachment,
 * and ephemeral WebSocket streaming bound to the active StudySession.
 */
import React, {
  createContext,
  useContext,
  useState,
  useRef,
  useEffect,
  useCallback,
  ReactNode,
} from 'react';
import {
  LiveTransportState,
  LiveTransportMetrics,
  LiveTransportContextValue,
} from '../types/liveTransport';
import {
  requestCameraStream,
  stopCameraStream,
  LiveWebSocketClient,
} from '../services/liveTransport';
import { useSession } from './SessionContext';
import { useAuth } from './AuthContext';

const initialMetrics: LiveTransportMetrics = {
  framesSent: 0,
  framesDropped: 0,
  bytesSent: 0,
  connectedAt: null,
  lastAckReceived: null,
};

const LiveTransportContext = createContext<LiveTransportContextValue | undefined>(undefined);

export const LiveTransportProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { activeSession } = useSession();
  const { isAuthenticated } = useAuth();

  const [state, setState] = useState<LiveTransportState>('idle');
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [metrics, setMetrics] = useState<LiveTransportMetrics>(initialMetrics);
  const [error, setError] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const clientRef = useRef<LiveWebSocketClient | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Sync streamRef with stream state for cleanup hooks
  useEffect(() => {
    streamRef.current = stream;
  }, [stream]);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  /**
   * Stop active live session, release camera tracks, and close WebSocket.
   */
  const stopLiveSession = useCallback(() => {
    setState('stopping');

    // 1. Disconnect WebSocket and stop capture interval
    if (clientRef.current) {
      clientRef.current.disconnect('User stopped live session');
      clientRef.current = null;
    }

    // 2. Stop camera hardware stream tracks
    if (streamRef.current) {
      stopCameraStream(streamRef.current);
      streamRef.current = null;
    }
    setStream(null);

    // 3. Clear video element preview
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    setState('idle');
  }, []);

  /**
   * Start live session: acquire camera with video-only, attach preview, and open WebSocket.
   */
  const startLiveSession = useCallback(async () => {
    if (!activeSession) {
      setError('Please start a Study Session first before beginning live camera monitoring.');
      return;
    }

    if (state === 'connecting' || state === 'connected' || state === 'starting_camera') {
      return;
    }

    setError(null);
    setState('starting_camera');

    let mediaStream: MediaStream | null = null;
    try {
      // 1. Request camera permission (video: true, audio: false)
      mediaStream = await requestCameraStream();
      setStream(mediaStream);
      streamRef.current = mediaStream;

      // 2. Attach preview to video element
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
        await videoRef.current.play().catch(() => {
          // Auto-play policy handled via muted attribute
        });
      }

      setState('camera_ready');

      // 3. Initialize WebSocket transport client
      const client = new LiveWebSocketClient(activeSession.id, {
        onStateChange: (newState) => {
          setState(newState);
        },
        onMetricsUpdate: (newMetrics) => {
          setMetrics((prev) => ({ ...prev, ...newMetrics }));
        },
        onError: (errMessage) => {
          setError(errMessage);
        },
      });

      if (videoRef.current) {
        client.attachVideoElement(videoRef.current);
      }

      clientRef.current = client;

      // 4. Connect WebSocket
      client.connect();
    } catch (err: any) {
      if (mediaStream) {
        stopCameraStream(mediaStream);
      }
      setStream(null);
      streamRef.current = null;

      if (err.message === 'PERMISSION_DENIED') {
        setState('permission_denied');
        setError('Camera permission was denied. Please allow camera access in your browser settings.');
      } else if (err.message === 'CAMERA_UNAVAILABLE') {
        setState('camera_unavailable');
        setError('No camera device detected or camera is in use by another application.');
      } else {
        setState('connection_error');
        setError(err.message || 'Failed to start live camera session.');
      }
    }
  }, [activeSession, state]);

  /**
   * Reconnect live transport reusing the same session ID.
   */
  const reconnectLiveSession = useCallback(async () => {
    stopLiveSession();
    await startLiveSession();
  }, [stopLiveSession, startLiveSession]);

  // Lifecycle Coordination 1: When study session ends or becomes null, automatically stop live transport
  useEffect(() => {
    if (!activeSession && (state === 'connected' || state === 'connecting' || streamRef.current)) {
      stopLiveSession();
    }
  }, [activeSession, state, stopLiveSession]);

  // Lifecycle Coordination 2: When user logs out, immediately stop live transport
  useEffect(() => {
    if (!isAuthenticated && (state === 'connected' || state === 'connecting' || streamRef.current)) {
      stopLiveSession();
    }
  }, [isAuthenticated, state, stopLiveSession]);

  // Lifecycle Coordination 3: On component unmount, release all camera tracks and socket
  useEffect(() => {
    return () => {
      if (clientRef.current) {
        clientRef.current.disconnect('Component unmounted');
        clientRef.current = null;
      }
      if (streamRef.current) {
        stopCameraStream(streamRef.current);
        streamRef.current = null;
      }
    };
  }, []);

  const value: LiveTransportContextValue = {
    state,
    stream,
    videoRef: videoRef as React.RefObject<HTMLVideoElement>,
    metrics,
    error,
    isLive: state === 'connected',
    startLiveSession,
    stopLiveSession,
    reconnectLiveSession,
    clearError,
  };

  return (
    <LiveTransportContext.Provider value={value}>
      {children}
    </LiveTransportContext.Provider>
  );
};

export const useLiveTransport = (): LiveTransportContextValue => {
  const context = useContext(LiveTransportContext);
  if (!context) {
    throw new Error('useLiveTransport must be used within a LiveTransportProvider');
  }
  return context;
};
