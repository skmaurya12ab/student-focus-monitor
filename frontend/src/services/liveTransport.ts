/**
 * Live Camera and WebSocket Transport Service (Phase 7).
 * Encapsulates camera acquisition, canvas frame downsampling, paced WebSocket transmission,
 * backpressure control, and reconnect handling.
 */
import {
  LiveTransportMetrics,
  LiveTransportState,
  LiveDetectionResult,
} from '../types/liveTransport';

const DEFAULT_TARGET_FPS = 5;
const MAX_BUFFERED_AMOUNT_BYTES = 256 * 1024; // 256 KB backpressure limit
const FRAME_JPEG_QUALITY = 0.7;
const FRAME_MAX_WIDTH = 480;
const FRAME_MAX_HEIGHT = 360;

/**
 * Acquire user camera stream with video only (NO microphone).
 */
export async function requestCameraStream(): Promise<MediaStream> {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    throw new Error('CAMERA_UNAVAILABLE');
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 640, max: 640 },
        height: { ideal: 480, max: 480 },
        frameRate: { ideal: 15, max: 15 },
      },
      audio: false, // Strictly NO microphone requested
    });
    return stream;
  } catch (err: any) {
    if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
      throw new Error('PERMISSION_DENIED');
    }
    if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
      throw new Error('CAMERA_UNAVAILABLE');
    }
    throw new Error(err.message || 'CAMERA_ERROR');
  }
}

/**
 * Cleanly stop all tracks on a MediaStream.
 */
export function stopCameraStream(stream: MediaStream | null): void {
  if (!stream) return;
  stream.getTracks().forEach((track) => {
    try {
      track.stop();
    } catch {
      // Ignore errors on stopping tracks
    }
  });
}

/**
 * Construct WebSocket URL for the given session ID.
 */
export function getWebSocketUrl(sessionId: string): string {
  const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  const wsProto = apiUrl.startsWith('https') ? 'wss:' : 'ws:';
  const host = apiUrl.replace(/^https?:\/\//, '');
  return `${wsProto}//${host}/api/ws/sessions/${sessionId}`;
}

export interface LiveTransportCallbacks {
  onStateChange: (state: LiveTransportState) => void;
  onMetricsUpdate: (metrics: Partial<LiveTransportMetrics>) => void;
  onError: (error: string) => void;
  onDetectionResult?: (result: LiveDetectionResult) => void;
}

/**
 * Live WebSocket client managing paced frame transmission with backpressure protection.
 */
export class LiveWebSocketClient {
  private sessionId: string;
  private socket: WebSocket | null = null;
  private videoEl: HTMLVideoElement | null = null;
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D | null;
  private captureIntervalId: any = null;
  private isSendingFrame = false;
  private isExplicitlyClosed = false;
  private targetFps = DEFAULT_TARGET_FPS;
  private callbacks: LiveTransportCallbacks;

  // Ephemeral client-side metrics
  private framesSent = 0;
  private framesDropped = 0;
  private bytesSent = 0;

  constructor(sessionId: string, callbacks: LiveTransportCallbacks) {
    this.sessionId = sessionId;
    this.callbacks = callbacks;
    if (typeof document !== 'undefined') {
      this.canvas = document.createElement('canvas');
      this.canvas.width = FRAME_MAX_WIDTH;
      this.canvas.height = FRAME_MAX_HEIGHT;
      this.ctx = this.canvas.getContext('2d');
    } else {
      this.canvas = null as any;
      this.ctx = null;
    }
  }

  /**
   * Attach the active HTMLVideoElement preview source.
   */
  public attachVideoElement(video: HTMLVideoElement): void {
    this.videoEl = video;
  }

  /**
   * Connect to WebSocket live transport endpoint.
   */
  public connect(): void {
    this.isExplicitlyClosed = false;
    this.callbacks.onStateChange('connecting');

    const url = getWebSocketUrl(this.sessionId);
    try {
      this.socket = new WebSocket(url);
      this.socket.binaryType = 'arraybuffer';

      this.socket.onopen = () => {
        // Socket opened; waiting for server "ready" protocol message
      };

      this.socket.onmessage = (event) => {
        if (typeof event.data === 'string') {
          try {
            const data = JSON.parse(event.data);
            this.handleServerMessage(data);
          } catch {
            // Non-JSON string message ignored
          }
        }
      };

      this.socket.onerror = () => {
        if (!this.isExplicitlyClosed) {
          this.callbacks.onError('WebSocket connection error');
          this.callbacks.onStateChange('connection_error');
        }
      };

      this.socket.onclose = (event) => {
        this.stopCaptureLoop();
        if (this.isExplicitlyClosed) {
          this.callbacks.onStateChange('idle');
        } else {
          this.callbacks.onStateChange('disconnected');
          if (event.code === 1008) {
            this.callbacks.onError(`Connection rejected: ${event.reason || 'Policy violation'}`);
          }
        }
      };
    } catch (err: any) {
      this.callbacks.onError(err.message || 'Failed to initialize WebSocket');
      this.callbacks.onStateChange('connection_error');
    }
  }

  /**
   * Handle server control/acknowledgement messages.
   */
  private handleServerMessage(data: any): void {
    if (data.type === 'ready') {
      if (data.target_fps && typeof data.target_fps === 'number') {
        this.targetFps = data.target_fps;
      }
      this.callbacks.onStateChange('connected');
      this.callbacks.onMetricsUpdate({
        connectedAt: new Date().toISOString(),
      });
      this.startCaptureLoop(this.targetFps);
    } else if (data.type === 'ack') {
      this.callbacks.onMetricsUpdate({
        lastAckReceived: {
          framesReceived: data.frames_received,
          bytesReceived: data.bytes_received,
        },
      });
    } else if (data.type === 'detection_result') {
      if (this.callbacks.onDetectionResult) {
        this.callbacks.onDetectionResult(data as LiveDetectionResult);
      }
    } else if (data.type === 'closed') {
      this.disconnect('Server closed transport');
    }
  }

  /**
   * Start frame capture and transmission loop at target FPS.
   */
  public startCaptureLoop(fps: number = DEFAULT_TARGET_FPS): void {
    this.stopCaptureLoop();
    const intervalMs = Math.round(1000 / fps);

    this.captureIntervalId = setInterval(() => {
      this.captureAndSendFrame();
    }, intervalMs);
  }

  /**
   * Stop frame capture interval.
   */
  public stopCaptureLoop(): void {
    if (this.captureIntervalId !== null) {
      clearInterval(this.captureIntervalId);
      this.captureIntervalId = null;
    }
  }

  /**
   * Capture a single video frame, resize to canvas, encode to JPEG, and transmit via WebSocket.
   * Employs backpressure: drops frame if socket buffer is congested or send is currently in flight.
   */
  private captureAndSendFrame(): void {
    if (
      !this.socket ||
      this.socket.readyState !== WebSocket.OPEN ||
      !this.videoEl ||
      this.videoEl.readyState < HTMLMediaElement.HAVE_CURRENT_DATA
    ) {
      return;
    }

    // Backpressure check 1: previous frame still encoding/sending
    if (this.isSendingFrame) {
      this.framesDropped++;
      this.callbacks.onMetricsUpdate({ framesDropped: this.framesDropped });
      return;
    }

    // Backpressure check 2: WebSocket outgoing buffer congested
    if (this.socket.bufferedAmount > MAX_BUFFERED_AMOUNT_BYTES) {
      this.framesDropped++;
      this.callbacks.onMetricsUpdate({ framesDropped: this.framesDropped });
      return;
    }

    if (!this.ctx) return;

    this.isSendingFrame = true;

    try {
      // Draw scaled video frame onto hidden offscreen canvas
      this.ctx.drawImage(
        this.videoEl,
        0,
        0,
        this.videoEl.videoWidth || FRAME_MAX_WIDTH,
        this.videoEl.videoHeight || FRAME_MAX_HEIGHT,
        0,
        0,
        this.canvas.width,
        this.canvas.height
      );

      // Convert to compressed JPEG blob
      this.canvas.toBlob(
        async (blob) => {
          try {
            if (blob && this.socket && this.socket.readyState === WebSocket.OPEN) {
              const buffer = await blob.arrayBuffer();
              this.socket.send(buffer);
              this.framesSent++;
              this.bytesSent += buffer.byteLength;
              this.callbacks.onMetricsUpdate({
                framesSent: this.framesSent,
                bytesSent: this.bytesSent,
              });
            }
          } catch {
            this.framesDropped++;
            this.callbacks.onMetricsUpdate({ framesDropped: this.framesDropped });
          } finally {
            this.isSendingFrame = false;
          }
        },
        'image/jpeg',
        FRAME_JPEG_QUALITY
      );
    } catch {
      this.isSendingFrame = false;
    }
  }

  /**
   * Gracefully disconnect WebSocket and clean up capture loop.
   */
  public disconnect(reason?: string): void {
    this.isExplicitlyClosed = true;
    this.stopCaptureLoop();

    if (this.socket) {
      try {
        if (this.socket.readyState === WebSocket.OPEN) {
          this.socket.send(JSON.stringify({ type: 'stop', reason }));
          this.socket.close(1000, reason || 'Normal closure');
        } else if (this.socket.readyState === WebSocket.CONNECTING) {
          this.socket.close(1000, 'Cancelled during connecting');
        }
      } catch {
        // Socket close ignored
      }
      this.socket = null;
    }

    this.callbacks.onStateChange('idle');
  }
}
