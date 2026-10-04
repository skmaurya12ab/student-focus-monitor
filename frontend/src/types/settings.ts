/**
 * User Settings types and API contract (Phase 9 Correction).
 */

export interface UserSettings {
  looking_away_delay_seconds: number;
  phone_use_delay_seconds: number;
  yawning_delay_seconds: number;
  drowsy_delay_seconds: number;
  leaning_back_delay_seconds: number;
  away_from_desk_delay_seconds: number;
  sound_alerts_enabled: boolean;
  banner_alerts_enabled: boolean;
  session_end_summary_enabled: boolean;
  camera_device: string;
  preview_quality: string;
}

export type UserSettingsUpdatePayload = Partial<UserSettings>;
