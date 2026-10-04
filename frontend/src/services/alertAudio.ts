/**
 * Browser-compatible Web Audio API alert feedback service (Phase 9 Correction).
 *
 * Implements managed repeating/pulsating audio feedback:
 * - Distraction starts -> pulsating alert begins immediately.
 * - Distraction continues -> pulses repeat continuously (250ms beep + 550ms pause).
 * - Distraction clears -> repeating alert stops immediately.
 * - Single managed timer: multiple incoming WebSocket messages or multiple simultaneous
 *   active detectors NEVER create duplicate overlapping audio loops.
 * - Maximum application volume (Gain = 1.0) while respecting system/browser volume.
 * - AudioContext unlocked via user interaction gesture.
 */

export interface AlertSoundOptions {
  muted?: boolean;
  volume?: number;
  pulseDurationMs?: number;
  pulseSilenceMs?: number;
}

export class AlertSoundManager {
  private activeCategories: Set<string> = new Set<string>();
  private audioCtx: AudioContext | null = null;
  private isMuted: boolean = false;
  private volume: number = 1.0; // Maximum usable application-level volume
  private pulseTimer: ReturnType<typeof setInterval> | null = null;
  private isPulsating: boolean = false;
  private pulseDurationMs: number = 250;
  private pulseSilenceMs: number = 550;

  constructor(options?: AlertSoundOptions) {
    if (options?.muted !== undefined) {
      this.isMuted = options.muted;
    }
    if (options?.volume !== undefined) {
      this.volume = options.volume;
    }
    if (options?.pulseDurationMs !== undefined) {
      this.pulseDurationMs = options.pulseDurationMs;
    }
    if (options?.pulseSilenceMs !== undefined) {
      this.pulseSilenceMs = options.pulseSilenceMs;
    }
  }

  /**
   * Initialize or resume Web Audio AudioContext upon user gesture.
   */
  public initOnUserGesture(): void {
    try {
      if (!this.audioCtx) {
        const globalScope = typeof window !== 'undefined' ? window : (globalThis as any);
        const AudioContextClass =
          globalScope?.AudioContext || (globalScope as any)?.webkitAudioContext;
        if (AudioContextClass) {
          this.audioCtx = new AudioContextClass();
        }
      }

      if (this.audioCtx && this.audioCtx.state === 'suspended') {
        this.audioCtx.resume().catch(() => {
          // Autoplay policy may still be locked until next user gesture
        });
      }
    } catch {
      // AudioContext creation failure ignored safely
    }
  }

  /**
   * Handle active detection category updates.
   * Starts pulsating beep when distraction begins.
   * Maintains single ongoing loop while distraction continues.
   * Stops immediately when all distractions clear.
   *
   * @param currentCategories Array of active detector category strings (e.g. ['phone_use', 'looking_away'])
   * @returns boolean true if the alert is actively pulsating
   */
  public updateActiveDetections(currentCategories: string[]): boolean {
    const isDistracted = currentCategories.length > 0;
    this.activeCategories = new Set(currentCategories);

    if (isDistracted) {
      if (!this.isPulsating) {
        this.startPulsatingAlert();
      }
      return true;
    } else {
      if (this.isPulsating) {
        this.stopPulsatingAlert();
      }
      return false;
    }
  }

  /**
   * Start managed pulsating alert loop.
   */
  public startPulsatingAlert(): void {
    if (this.isPulsating) return; // Prevent duplicate timers
    this.isPulsating = true;

    // Play first pulse immediately
    this.playBeepPulse();

    const periodMs = this.pulseDurationMs + this.pulseSilenceMs;
    this.pulseTimer = setInterval(() => {
      this.playBeepPulse();
    }, periodMs);
  }

  /**
   * Stop managed pulsating alert loop immediately.
   */
  public stopPulsatingAlert(): void {
    if (this.pulseTimer !== null) {
      clearInterval(this.pulseTimer);
      this.pulseTimer = null;
    }
    this.isPulsating = false;
    this.activeCategories.clear();
  }

  /**
   * Alias for stopping alert (e.g. on unmount or session stop).
   */
  public stop(): void {
    this.stopPulsatingAlert();
  }

  /**
   * Synthesize a single audible alert beep pulse (250ms) using Web Audio API.
   * Application-level gain is set to maximum usable level (1.0).
   */
  public playBeepPulse(): void {
    if (this.isMuted) return;

    try {
      this.initOnUserGesture();
      if (!this.audioCtx) return;

      if (this.audioCtx.state === 'suspended') {
        this.audioCtx.resume().catch(() => {});
      }

      if (this.audioCtx.state !== 'running') return;

      const now = this.audioCtx.currentTime;
      const osc = this.audioCtx.createOscillator();
      const gain = this.audioCtx.createGain();

      // Clear, prominent dual-frequency attention beep: 880 Hz (A5)
      osc.type = 'sine';
      osc.frequency.setValueAtTime(880.0, now);

      const durationSec = this.pulseDurationMs / 1000.0;
      const rampEnd = Math.max(0.01, durationSec - 0.03);

      // Max usable application volume
      gain.gain.setValueAtTime(this.volume, now);
      gain.gain.setValueAtTime(this.volume, now + rampEnd);
      // Clean de-click ramp down right before stop
      gain.gain.linearRampToValueAtTime(0.001, now + durationSec);

      osc.connect(gain);
      gain.connect(this.audioCtx.destination);

      osc.start(now);
      osc.stop(now + durationSec);

      // Node cleanup
      osc.onended = () => {
        try {
          osc.disconnect();
          gain.disconnect();
        } catch {
          // Ignore
        }
      };
    } catch {
      // Audio errors caught cleanly without breaking UI
    }
  }

  /**
   * Reset all state.
   */
  public reset(): void {
    this.stopPulsatingAlert();
  }

  /**
   * Set mute state (e.g. from user Settings).
   */
  public setMuted(muted: boolean): void {
    this.isMuted = muted;
    if (muted && this.isPulsating) {
      // Suppress active audio loop
      this.stopPulsatingAlert();
    }
  }

  /**
   * Check if currently muted.
   */
  public getIsMuted(): boolean {
    return this.isMuted;
  }

  /**
   * Check if currently pulsating.
   */
  public getIsPulsating(): boolean {
    return this.isPulsating;
  }

  /**
   * Get application volume level.
   */
  public getVolume(): number {
    return this.volume;
  }

  /**
   * Get list of currently tracked active categories.
   */
  public getTrackedCategories(): string[] {
    return Array.from(this.activeCategories);
  }

  /**
   * Teardown audio context and timers completely.
   */
  public close(): void {
    this.stopPulsatingAlert();
    if (this.audioCtx) {
      try {
        this.audioCtx.close().catch(() => {});
      } catch {
        // Ignored
      }
      this.audioCtx = null;
    }
  }
}

// Global singleton instance for easy app-wide access
export const alertSoundManager = new AlertSoundManager();
