import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { AlertSoundManager } from './alertAudio';

describe('AlertSoundManager (Phase 9 Correction Repeating Audio Feedback)', () => {
  let mockOscillator: any;
  let mockGain: any;
  let mockAudioContext: any;
  let manager: AlertSoundManager;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.restoreAllMocks();

    mockOscillator = {
      type: '',
      frequency: {
        setValueAtTime: vi.fn(),
      },
      connect: vi.fn(),
      start: vi.fn(),
      stop: vi.fn(),
      disconnect: vi.fn(),
    };

    mockGain = {
      gain: {
        setValueAtTime: vi.fn(),
        linearRampToValueAtTime: vi.fn(),
      },
      connect: vi.fn(),
      disconnect: vi.fn(),
    };

    mockAudioContext = {
      state: 'running',
      currentTime: 10.0,
      destination: {},
      createOscillator: vi.fn(() => mockOscillator),
      createGain: vi.fn(() => mockGain),
      resume: vi.fn().mockResolvedValue(undefined),
      close: vi.fn().mockResolvedValue(undefined),
    };

    const audioContextCtor = vi.fn(() => mockAudioContext);
    vi.stubGlobal('AudioContext', audioContextCtor);
    vi.stubGlobal('window', {
      AudioContext: audioContextCtor,
    });

    manager = new AlertSoundManager({ volume: 1.0, pulseDurationMs: 250, pulseSilenceMs: 550 });
    manager.initOnUserGesture();
  });

  afterEach(() => {
    if (manager) {
      manager.close();
    }
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it('A. distraction starts -> repeating alert starts and plays immediate pulse', () => {
    const isPulsing = manager.updateActiveDetections(['phone_use']);
    expect(isPulsing).toBe(true);
    expect(manager.getIsPulsating()).toBe(true);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(1);
    expect(mockOscillator.start).toHaveBeenCalledTimes(1);
  });

  it('B. subsequent detection_result messages while distracted do NOT create duplicate loops', () => {
    manager.updateActiveDetections(['phone_use']);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(1);

    // 2nd message arrives while still distracted
    manager.updateActiveDetections(['phone_use']);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(1);

    // 3rd message arrives
    manager.updateActiveDetections(['phone_use']);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(1);
  });

  it('C. distraction remains active -> multiple beep pulses occur across intervals', () => {
    manager.updateActiveDetections(['phone_use']);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(1);

    // Advance 800ms (250ms beep + 550ms silence)
    vi.advanceTimersByTime(800);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(2);

    // Advance another 800ms
    vi.advanceTimersByTime(800);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(3);
  });

  it('D. distraction clears -> alert stops immediately and no further pulses occur', () => {
    manager.updateActiveDetections(['looking_away']);
    expect(manager.getIsPulsating()).toBe(true);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(1);

    // Focus restored: empty categories
    const isPulsing = manager.updateActiveDetections([]);
    expect(isPulsing).toBe(false);
    expect(manager.getIsPulsating()).toBe(false);

    // Advance time: verify no additional pulses are scheduled
    vi.advanceTimersByTime(2000);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(1);
  });

  it('E. live session ends -> alert stops and audio timers are cleaned', () => {
    manager.updateActiveDetections(['yawning']);
    expect(manager.getIsPulsating()).toBe(true);

    manager.stop();
    expect(manager.getIsPulsating()).toBe(false);

    vi.advanceTimersByTime(1600);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(1);
  });

  it('F. component unmounts -> close cleanly terminates all timers and audio context', () => {
    manager.updateActiveDetections(['drowsy']);
    expect(manager.getIsPulsating()).toBe(true);

    manager.close();
    expect(manager.getIsPulsating()).toBe(false);
    expect(mockAudioContext.close).toHaveBeenCalledTimes(1);
  });

  it('G. multiple active detectors -> still only one distraction alert sound loop', () => {
    manager.updateActiveDetections(['looking_away', 'phone_use']);
    expect(manager.getIsPulsating()).toBe(true);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(1);

    // Multiple detections continue
    manager.updateActiveDetections(['looking_away', 'phone_use', 'leaning_back']);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(1);

    // Only one pulse loop running across intervals
    vi.advanceTimersByTime(800);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(2);
  });

  it('H. application gain is configured at maximum application level (1.0)', () => {
    expect(manager.getVolume()).toBe(1.0);
    manager.playBeepPulse();
    expect(mockGain.gain.setValueAtTime).toHaveBeenCalledWith(1.0, 10.0);
  });

  it('respects muted option and suppresses beep pulses when sound alerts are disabled', () => {
    manager.setMuted(true);
    expect(manager.getIsMuted()).toBe(true);

    manager.updateActiveDetections(['phone_use']);
    expect(mockAudioContext.createOscillator).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1600);
    expect(mockAudioContext.createOscillator).not.toHaveBeenCalled();
  });
});
