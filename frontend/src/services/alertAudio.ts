/**
 * Browser-compatible Web Audio API alert feedback service (Phase 9).
 * Implements strict edge-triggered deduplication:
 * - Alert starts -> plays chime once.
 * - Alert continues -> no repeated sound spam.
 * - Alert ends -> resets edge state.
 * - Alert starts again later -> plays chime once.
 */

export interface AlertSoundOptions {
  muted?: boolean;
  volume?: number;
}

export class AlertSoundManager {
  private activeCategories: Set<string> = new Set<string>();
  private audioCtx: AudioContext | null = null;
  private isMuted: boolean = false;
  private volume: number = 0.18;

  constructor(options?: AlertSoundOptions) {
    if (options?.muted !== undefined) {
      this.isMuted = options.muted;
    }
    if (options?.volume !== undefined) {
      this.volume = options.volume;
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
   * Handle active detection category transitions.
   * Edge-triggered: plays chime once if ANY new category enters active set.
   * Does NOT repeat if the alert continues without new categories.
   * Resets when all categories clear.
   *
   * @param currentCategories Array of active detector category strings (e.g. ['looking_away'])
   * @returns boolean true if a new alert edge fired and sound was played
   */
  public updateActiveDetections(currentCategories: string[]): boolean {
    const currentSet = new Set(currentCategories);

    // If completely clear, reset edge tracking
    if (currentSet.size === 0) {
      this.activeCategories.clear();
      return false;
    }

    // Check if there is any new category not previously active
    let hasNewCategory = false;
    for (const cat of currentSet) {
      if (!this.activeCategories.has(cat)) {
        hasNewCategory = true;
        break;
      }
    }

    // Update active set
    this.activeCategories = currentSet;

    if (hasNewCategory) {
      this.playAlertTone();
      return true;
    }

    return false;
  }

  /**
   * Reset all edge tracking state.
   */
  public reset(): void {
    this.activeCategories.clear();
  }

  /**
   * Set mute state.
   */
  public setMuted(muted: boolean): void {
    this.isMuted = muted;
  }

  /**
   * Check if currently muted.
   */
  public getIsMuted(): boolean {
    return this.isMuted;
  }

  /**
   * Get list of currently tracked active categories.
   */
  public getTrackedCategories(): string[] {
    return Array.from(this.activeCategories);
  }

  /**
   * Synthesize pleasant alert chime using Web Audio API oscillator.
   */
  public playAlertTone(): void {
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

      osc.type = 'sine';
      // Harmonic dual-frequency alert tone: 523.25Hz (C5) ramping to 659.25Hz (E5)
      osc.frequency.setValueAtTime(523.25, now);
      osc.frequency.exponentialRampToValueAtTime(659.25, now + 0.12);

      gain.gain.setValueAtTime(this.volume, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);

      osc.connect(gain);
      gain.connect(this.audioCtx.destination);

      osc.start(now);
      osc.stop(now + 0.35);
    } catch {
      // Audio playback errors handled gracefully without bubbling
    }
  }

  /**
   * Teardown audio context if needed.
   */
  public close(): void {
    if (this.audioCtx) {
      try {
        this.audioCtx.close().catch(() => {});
      } catch {
        // Ignored
      }
      this.audioCtx = null;
    }
    this.activeCategories.clear();
  }
}

// Global singleton instance for easy app-wide access
export const alertSoundManager = new AlertSoundManager();
