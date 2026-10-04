import React, { useState, useEffect, useCallback } from 'react';
import { SettingsData } from '../../types/dashboard';
import { ExportCloverIcon, ChevronDownIcon } from '../../components/common/Icons';
import { useAuth } from '../../context/AuthContext';
import { fetchUserSettings, updateUserSettings } from '../../services/settingsApi';
import { alertSoundManager } from '../../services/alertAudio';
import { UserSettings } from '../../types/settings';

interface SettingsPageProps {
  data: SettingsData;
  onNavigateToAccount?: () => void;
}

export const SettingsPage: React.FC<SettingsPageProps> = ({ data, onNavigateToAccount }) => {
  const { user, isAuthenticated } = useAuth();
  const [thresholds, setThresholds] = useState(data.thresholds);
  const [notifications, setNotifications] = useState(data.notifications);
  const [cameraDevice, setCameraDevice] = useState(data.webcam.selectedDevice);
  const [isSavedMessage, setIsSavedMessage] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Load authoritative user settings from backend
  const loadSettings = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const s: UserSettings = await fetchUserSettings();
      setThresholds([
        { id: 'thresh-1', label: 'Yawning', seconds: Math.round(s.yawning_delay_seconds), maxSeconds: 10 },
        { id: 'thresh-2', label: 'Phone use', seconds: Math.round(s.phone_use_delay_seconds), maxSeconds: 10 },
        { id: 'thresh-3', label: 'Bad posture', seconds: Math.round(s.leaning_back_delay_seconds), maxSeconds: 10 },
        { id: 'thresh-4', label: 'Sleeping posture', seconds: Math.round(s.drowsy_delay_seconds), maxSeconds: 10 },
        { id: 'thresh-5', label: 'Away from seat', seconds: Math.round(s.away_from_desk_delay_seconds), maxSeconds: 10 },
      ]);
      setNotifications([
        { id: 'notif-1', label: 'Beep / sound alerts', enabled: s.sound_alerts_enabled },
        { id: 'notif-2', label: 'On-screen banner alerts', enabled: s.banner_alerts_enabled },
        { id: 'notif-3', label: 'Session end summary', enabled: s.session_end_summary_enabled },
      ]);
      if (s.camera_device) {
        setCameraDevice(s.camera_device);
      }
      alertSoundManager.setMuted(!s.sound_alerts_enabled);
    } catch {
      // Fallback to data defaults gracefully if network/auth not ready
    }
  }, [isAuthenticated]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const adjustThreshold = (id: string, newSeconds: number) => {
    setThresholds((prev) =>
      prev.map((item) =>
        item.id === id
          ? { ...item, seconds: Math.max(1, Math.min(item.maxSeconds, newSeconds)) }
          : item
      )
    );
  };

  const toggleNotification = (id: string) => {
    setNotifications((prev) =>
      prev.map((item) =>
        item.id === id ? { ...item, enabled: !item.enabled } : item
      )
    );
  };

  const handleSave = async () => {
    setIsSaving(true);
    setErrorMessage(null);

    const threshMap = Object.fromEntries(thresholds.map((t) => [t.id, t.seconds]));
    const notifMap = Object.fromEntries(notifications.map((n) => [n.id, n.enabled]));

    const payload = {
      yawning_delay_seconds: threshMap['thresh-1'] ?? 2.0,
      phone_use_delay_seconds: threshMap['thresh-2'] ?? 6.0,
      leaning_back_delay_seconds: threshMap['thresh-3'] ?? 8.0,
      drowsy_delay_seconds: threshMap['thresh-4'] ?? 4.0,
      away_from_desk_delay_seconds: threshMap['thresh-5'] ?? 10.0,
      sound_alerts_enabled: notifMap['notif-1'] ?? true,
      banner_alerts_enabled: notifMap['notif-2'] ?? true,
      session_end_summary_enabled: notifMap['notif-3'] ?? false,
      camera_device: cameraDevice,
    };

    try {
      if (isAuthenticated) {
        await updateUserSettings(payload);
      }
      alertSoundManager.setMuted(!payload.sound_alerts_enabled);
      setIsSavedMessage(true);
      setTimeout(() => setIsSavedMessage(false), 2500);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to save settings');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="sfm-page sfm-settings-page" id="settings-page">
      {/* Error banner if save fails */}
      {errorMessage && (
        <div className="sfm-account-banner sfm-account-banner-offline" role="alert" style={{ marginBottom: 16 }}>
          <span>⚠️ {errorMessage}</span>
          <button type="button" className="sfm-btn-retry" onClick={() => setErrorMessage(null)}>
            Dismiss
          </button>
        </div>
      )}

      {/* Header */}
      <header className="sfm-page-header">
        <div className="sfm-header-left">
          <div className="sfm-avatar-circle" aria-label="User Avatar">
            <span>N</span>
          </div>
          <div className="sfm-header-titles">
            <h1 className="sfm-page-title">{data.title}</h1>
            <p className="sfm-page-subtitle">{data.subtitle}</p>
          </div>
        </div>

        <div className="sfm-header-right">
          <div className="sfm-profile-shortcut-badge" aria-label="User profile shortcut">
            <span>S</span>
          </div>

          <button
            type="button"
            className="sfm-icon-btn"
            aria-label="Export settings"
            title="Export settings"
          >
            <ExportCloverIcon size={18} />
          </button>
        </div>
      </header>

      {/* Grid Content */}
      <div className="sfm-content-grid">
        {/* Card 1: Alert Thresholds */}
        <section
          className="sfm-card sfm-card-full sfm-thresholds-card"
          aria-labelledby="thresholds-heading"
        >
          <div className="sfm-thresholds-header">
            <h2 id="thresholds-heading" className="sfm-card-heading">
              {data.thresholdsTitle}
            </h2>
            <p className="sfm-card-subheading">{data.thresholdsSubtitle}</p>
          </div>

          <div className="sfm-thresholds-list">
            {thresholds.map((item) => {
              const fillPercent = Math.min(
                100,
                Math.max(10, (item.seconds / item.maxSeconds) * 100)
              );
              return (
                <div key={item.id} className="sfm-threshold-row">
                  <span className="sfm-threshold-label">{item.label}</span>
                  <div
                    className="sfm-threshold-track-wrap"
                    onClick={(e) => {
                      const rect = e.currentTarget.getBoundingClientRect();
                      const clickX = e.clientX - rect.left;
                      const ratio = Math.max(0.1, Math.min(1, clickX / rect.width));
                      adjustThreshold(item.id, Math.round(ratio * item.maxSeconds));
                    }}
                    role="slider"
                    aria-label={`Adjust threshold for ${item.label}`}
                    aria-valuenow={item.seconds}
                    aria-valuemin={1}
                    aria-valuemax={item.maxSeconds}
                    tabIndex={0}
                  >
                    <div
                      className="sfm-threshold-track-fill"
                      style={{ width: `${fillPercent}%` }}
                    />
                  </div>
                  <span className="sfm-threshold-value">{item.seconds} sec</span>
                </div>
              );
            })}
          </div>
        </section>

        {/* 2-Column Row: Alerts & Webcam */}
        <div className="sfm-two-col-row">
          {/* Card 2: Alerts & Notifications */}
          <section
            className="sfm-card sfm-col-card sfm-alerts-card"
            aria-labelledby="alerts-heading"
          >
            <h2 id="alerts-heading" className="sfm-card-heading">
              {data.notificationsTitle}
            </h2>

            <div className="sfm-toggles-list">
              {notifications.map((item) => (
                <div key={item.id} className="sfm-toggle-row">
                  <span className="sfm-toggle-label">{item.label}</span>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={item.enabled}
                    className={`sfm-switch ${item.enabled ? 'is-on' : 'is-off'}`}
                    onClick={() => toggleNotification(item.id)}
                    aria-label={`Toggle ${item.label}`}
                  >
                    <span className="sfm-switch-handle" />
                  </button>
                </div>
              ))}
            </div>
          </section>

          {/* Card 3: Webcam */}
          <section
            className="sfm-card sfm-col-card sfm-webcam-card"
            aria-labelledby="webcam-heading"
          >
            <h2 id="webcam-heading" className="sfm-card-heading">
              {data.webcamTitle}
            </h2>

            <div className="sfm-webcam-body">
              <label htmlFor="camera-device-select" className="sfm-input-label">
                {data.webcam.deviceLabel}
              </label>

              <div className="sfm-select-wrap">
                <select
                  id="camera-device-select"
                  className="sfm-select-input"
                  value={cameraDevice}
                  onChange={(e) => setCameraDevice(e.target.value)}
                >
                  <option value="Integrated Camera - 720p">
                    Integrated Camera - 720p
                  </option>
                  <option value="External USB Camera - 1080p">
                    External USB Camera - 1080p
                  </option>
                </select>
                <div className="sfm-select-chevron" aria-hidden="true">
                  <ChevronDownIcon size={12} color="#171A24" />
                </div>
              </div>

              <div className="sfm-preview-quality-info">
                <span className="sfm-input-label">{data.webcam.previewQualityLabel}</span>
                <span className="sfm-quality-value">{data.webcam.qualityValue}</span>
              </div>
            </div>
          </section>
        </div>

        {/* Card 4: Profile */}
        <section
          className="sfm-card sfm-card-full sfm-profile-card"
          aria-labelledby="profile-heading"
        >
          <h2 id="profile-heading" className="sfm-card-heading">
            {data.profileTitle}
          </h2>

          <div className="sfm-profile-body">
            <div className="sfm-profile-left">
              <div className="sfm-profile-avatar-large" aria-label="Profile initial">
                <span>{user?.displayName ? user.displayName.charAt(0).toUpperCase() : data.profile.initial}</span>
              </div>
              <div className="sfm-profile-meta">
                <span className="sfm-profile-name">{user?.displayName || data.profile.name}</span>
                <span className="sfm-profile-account">{data.profile.accountType}</span>
              </div>
            </div>

            <div className="sfm-profile-actions">
              <button
                type="button"
                className="sfm-btn-secondary"
                id="btn-edit-profile"
                onClick={onNavigateToAccount}
                title="Go to Account settings"
              >
                Edit profile
              </button>
              <button
                type="button"
                className="sfm-btn-save-changes"
                onClick={handleSave}
                disabled={isSaving}
                id="btn-save-changes"
              >
                {isSaving ? 'Saving...' : isSavedMessage ? 'Saved ✓' : 'Save changes'}
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};
