import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { AlertSoundManager } from './alertAudio';

describe('AlertSoundManager (Phase 9 Web Audio Alert Feedback)', () => {
  let mockOscillator: any;
  let mockGain: any;
  let mockAudioContext: any;
  let manager: AlertSoundManager;

  beforeEach(() => {
    vi.restoreAllMocks();

    mockOscillator = {
      type: '',
      frequency: {
        setValueAtTime: vi.fn(),
        exponentialRampToValueAtTime: vi.fn(),
      },
      connect: vi.fn(),
      start: vi.fn(),
      stop: vi.fn(),
    };

    mockGain = {
      gain: {
        setValueAtTime: vi.fn(),
        exponentialRampToValueAtTime: vi.fn(),
      },
      connect: vi.fn(),
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

    manager = new AlertSoundManager();
    manager.initOnUserGesture();
  });

  afterEach(() => {
    if (manager) {
      manager.close();
    }
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it('triggers alert chime ONCE when an alert starts', () => {
    const fired = manager.updateActiveDetections(['looking_away']);
    expect(fired).toBe(true);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(1);
    expect(mockOscillator.start).toHaveBeenCalledTimes(1);
  });

  it('does NOT trigger repeated sound while alert remains sustained/active', () => {
    // 1st frame: alert starts
    const fired1 = manager.updateActiveDetections(['looking_away']);
    expect(fired1).toBe(true);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(1);

    // 2nd frame: sustained
    const fired2 = manager.updateActiveDetections(['looking_away']);
    expect(fired2).toBe(false);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(1);

    // 3rd frame: sustained
    const fired3 = manager.updateActiveDetections(['looking_away']);
    expect(fired3).toBe(false);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(1);
  });

  it('resets edge state when alert ends and fires again when alert restarts', () => {
    // 1. Alert starts
    expect(manager.updateActiveDetections(['phone_use'])).toBe(true);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(1);

    // 2. Alert continues
    expect(manager.updateActiveDetections(['phone_use'])).toBe(false);

    // 3. Alert clears (distraction resolved)
    expect(manager.updateActiveDetections([])).toBe(false);
    expect(manager.getTrackedCategories()).toHaveLength(0);

    // 4. Alert begins again later
    expect(manager.updateActiveDetections(['phone_use'])).toBe(true);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(2);
  });

  it('handles multiple active detections and triggers sound on newly added category', () => {
    // 1. Initial distraction: looking_away
    expect(manager.updateActiveDetections(['looking_away'])).toBe(true);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(1);

    // 2. Second simultaneous distraction arrives: phone_use added
    expect(manager.updateActiveDetections(['looking_away', 'phone_use'])).toBe(true);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(2);

    // 3. Both remain active: no repeated chime
    expect(manager.updateActiveDetections(['looking_away', 'phone_use'])).toBe(false);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(2);

    // 4. One ends, one remains: no chime since no NEW category was added
    expect(manager.updateActiveDetections(['phone_use'])).toBe(false);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(2);

    // 5. All end
    expect(manager.updateActiveDetections([])).toBe(false);

    // 6. Yawning begins: new chime
    expect(manager.updateActiveDetections(['yawning'])).toBe(true);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(3);
  });

  it('respects muted option and does not synthesize audio when muted', () => {
    manager.setMuted(true);
    expect(manager.getIsMuted()).toBe(true);

    const fired = manager.updateActiveDetections(['drowsy']);
    // updateActiveDetections returns true for state transition, but playAlertTone suppresses synthesis
    expect(fired).toBe(true);
    expect(mockAudioContext.createOscillator).not.toHaveBeenCalled();

    manager.setMuted(false);
    manager.reset();
    manager.updateActiveDetections(['drowsy']);
    expect(mockAudioContext.createOscillator).toHaveBeenCalledTimes(1);
  });

  it('safely handles suspended AudioContext by attempting resume on user gesture', async () => {
    mockAudioContext.state = 'suspended';
    manager.initOnUserGesture();
    expect(mockAudioContext.resume).toHaveBeenCalled();
  });
});
