import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  requestCameraStream,
  stopCameraStream,
  getWebSocketUrl,
  LiveWebSocketClient,
} from './liveTransport';

describe('liveTransport unit tests (Phase 7 Camera + WebSocket)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('requestCameraStream requests video only and strictly sets audio: false', async () => {
    const mockTrack = { stop: vi.fn() };
    const mockStream = {
      getTracks: () => [mockTrack],
    } as unknown as MediaStream;

    const getUserMediaMock = vi.fn().mockResolvedValue(mockStream);
    vi.stubGlobal('navigator', {
      mediaDevices: {
        getUserMedia: getUserMediaMock,
      },
    });

    const stream = await requestCameraStream();
    expect(stream).toBe(mockStream);

    expect(getUserMediaMock).toHaveBeenCalledWith(
      expect.objectContaining({
        video: expect.objectContaining({
          width: { ideal: 640, max: 640 },
          height: { ideal: 480, max: 480 },
          frameRate: { ideal: 15, max: 15 },
        }),
        audio: false, // MANDATORY: NO microphone requested
      })
    );
  });

  it('handles camera permission denied with code PERMISSION_DENIED', async () => {
    const err = new Error('Permission denied');
    err.name = 'NotAllowedError';
    vi.stubGlobal('navigator', {
      mediaDevices: {
        getUserMedia: vi.fn().mockRejectedValue(err),
      },
    });

    await expect(requestCameraStream()).rejects.toThrow('PERMISSION_DENIED');
  });

  it('handles camera unavailable with code CAMERA_UNAVAILABLE', async () => {
    const err = new Error('No camera found');
    err.name = 'NotFoundError';
    vi.stubGlobal('navigator', {
      mediaDevices: {
        getUserMedia: vi.fn().mockRejectedValue(err),
      },
    });

    await expect(requestCameraStream()).rejects.toThrow('CAMERA_UNAVAILABLE');
  });

  it('stopCameraStream safely terminates all tracks', () => {
    const mockTrack1 = { stop: vi.fn() };
    const mockTrack2 = { stop: vi.fn() };
    const mockStream = {
      getTracks: () => [mockTrack1, mockTrack2],
    } as unknown as MediaStream;

    stopCameraStream(mockStream);
    expect(mockTrack1.stop).toHaveBeenCalled();
    expect(mockTrack2.stop).toHaveBeenCalled();
  });

  it('getWebSocketUrl constructs canonical WebSocket route with active session ID', () => {
    const sessionId = 'd47ac10b-58cc-4372-a567-0e02b2c3d479';
    const url = getWebSocketUrl(sessionId);
    expect(url).toContain('/api/ws/sessions/d47ac10b-58cc-4372-a567-0e02b2c3d479');
    expect(url.startsWith('ws://') || url.startsWith('wss://')).toBe(true);
  });

  it('LiveWebSocketClient transitions to connecting, connected on ready, and stops cleanly', () => {
    const stateChanges: string[] = [];
    const metricsUpdates: any[] = [];
    const errors: string[] = [];

    class MockWebSocket {
      static OPEN = 1;
      static CONNECTING = 0;
      static CLOSED = 3;
      readyState = 1;
      binaryType = 'blob';
      bufferedAmount = 0;
      onopen: (() => void) | null = null;
      onmessage: ((ev: any) => void) | null = null;
      onerror: (() => void) | null = null;
      onclose: ((ev: any) => void) | null = null;
      send = vi.fn();
      close = vi.fn();

      constructor(public url: string) {
        setTimeout(() => {
          if (this.onopen) this.onopen();
          // Simulate server ready message
          if (this.onmessage) {
            this.onmessage({
              data: JSON.stringify({
                type: 'ready',
                session_id: 'd47ac10b-58cc-4372-a567-0e02b2c3d479',
                target_fps: 5,
                max_frame_size_bytes: 1048576,
              }),
            });
          }
        }, 10);
      }
    }

    vi.stubGlobal('WebSocket', MockWebSocket);

    const client = new LiveWebSocketClient('d47ac10b-58cc-4372-a567-0e02b2c3d479', {
      onStateChange: (state) => stateChanges.push(state),
      onMetricsUpdate: (m) => metricsUpdates.push(m),
      onError: (e) => errors.push(e),
    });

    client.connect();
    expect(stateChanges).toContain('connecting');

    // Wait for ready message simulation
    return new Promise<void>((resolve) => {
      setTimeout(() => {
        expect(stateChanges).toContain('connected');
        expect(metricsUpdates.length).toBeGreaterThan(0);
        expect(metricsUpdates[0].connectedAt).toBeDefined();

        // Test clean disconnect
        client.disconnect('User stopped');
        expect(stateChanges).toContain('idle');
        resolve();
      }, 50);
    });
  });

  it('LiveWebSocketClient handles connection rejection with policy violation', () => {
    const stateChanges: string[] = [];
    const errors: string[] = [];

    class RejectedWebSocket {
      onclose: ((ev: any) => void) | null = null;
      close = vi.fn();

      constructor() {
        setTimeout(() => {
          if (this.onclose) {
            this.onclose({ code: 1008, reason: 'Session is not active' });
          }
        }, 10);
      }
    }

    vi.stubGlobal('WebSocket', RejectedWebSocket);

    const client = new LiveWebSocketClient('d47ac10b-58cc-4372-a567-0e02b2c3d479', {
      onStateChange: (state) => stateChanges.push(state),
      onMetricsUpdate: () => {},
      onError: (e) => errors.push(e),
    });

    client.connect();

    return new Promise<void>((resolve) => {
      setTimeout(() => {
        expect(stateChanges).toContain('disconnected');
        expect(errors).toContain('Connection rejected: Session is not active');
        resolve();
      }, 50);
    });
  });
});
