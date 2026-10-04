import React, { useState, useEffect } from 'react';
import { HomeDashboardData } from '../../types/dashboard';
import {
  MascotBotIcon,
  ExportCloverIcon,
  PlayIcon,
  TargetFocusIcon,
  AlertTriangleIcon,
  AwayCircleIcon,
  LightningIcon,
  ClockTimeIcon,
} from '../../components/common/Icons';
import { useSession } from '../../context/SessionContext';
import { useAuth } from '../../context/AuthContext';
import { useLiveTransport } from '../../context/LiveTransportContext';
import { alertSoundManager } from '../../services/alertAudio';
import {
  resolveLiveBadgeStatus,
  getDetectorCategoryLabel,
  formatAlertDuration,
} from '../../utils/detectorLabels';
import { useFocusTimeline } from './useFocusTimeline';

interface HomePageProps {
  data: HomeDashboardData;
}

export const HomePage: React.FC<HomePageProps> = ({ data }) => {
  const {
    activeSession,
    lastCompletedSession,
    isStarting,
    isStopping,
    sessionError,
    elapsedSeconds,
    isBackendUnavailable,
    startSession,
    stopSession,
    clearSessionError,
    refreshActiveSession,
  } = useSession();
  const { isAuthenticated, user } = useAuth();
  const {
    state: liveState,
    videoRef,
    isLive,
    latestDetection,
    startLiveSession,
    stopLiveSession,
    error: liveError,
    clearError: clearLiveError,
  } = useLiveTransport();
  const [authNotice, setAuthNotice] = useState<boolean>(false);
  const [liveNotice, setLiveNotice] = useState<string | null>(null);

  // Focus timeline hook driven by real session state progression
  const timelineVM = useFocusTimeline(
    activeSession?.id,
    activeSession?.startedAt,
    latestDetection,
    isLive
  );

  // Audio alert transition feedback (Web Audio API with edge-triggered deduplication)
  useEffect(() => {
    if (!isLive || !latestDetection) {
      alertSoundManager.reset();
      return;
    }

    const activeCategories = latestDetection.active_detections?.map((d) => d.category) || [];
    if (latestDetection.state === 'distracted' && activeCategories.length === 0) {
      activeCategories.push('looking_away');
    }

    alertSoundManager.updateActiveDetections(activeCategories);
  }, [isLive, latestDetection]);

  // Teardown alert audio edge tracking on unmount
  useEffect(() => {
    return () => {
      alertSoundManager.reset();
    };
  }, []);

  const formatTimer = (totalSeconds: number): string => {
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    if (hours > 0) {
      return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  };

  const formatDurationHMS = (totalSeconds: number): string => {
    const sec = Math.max(0, Math.floor(totalSeconds));
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const formatDurationReadable = (totalSeconds: number): string => {
    const sec = Math.max(0, Math.floor(totalSeconds));
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    if (h > 0) {
      return `${h}h ${m}m`;
    }
    return `${m}m`;
  };

  // Authoritative current session: active session if in progress, else last completed session
  const currentSession = activeSession || lastCompletedSession;

  // Real metric values derived from live WebSocket stream when monitoring, or authoritative session record
  const focusedSeconds = (activeSession && latestDetection?.metrics)
    ? latestDetection.metrics.focused_seconds
    : (currentSession ? currentSession.focusedSeconds : 0);

  const distractedSeconds = (activeSession && latestDetection?.metrics)
    ? latestDetection.metrics.distracted_seconds
    : (currentSession ? currentSession.distractedSeconds : 0);

  const awaySeconds = (activeSession && latestDetection?.metrics)
    ? latestDetection.metrics.away_seconds
    : (currentSession ? currentSession.awaySeconds : 0);

  const studyTimeSeconds = activeSession
    ? elapsedSeconds
    : (currentSession ? currentSession.totalDurationSeconds : 0);

  const focusScoreVal = (activeSession && latestDetection?.metrics)
    ? latestDetection.metrics.focus_score
    : (currentSession?.focusScore !== null && currentSession?.focusScore !== undefined
      ? Number(currentSession.focusScore)
      : null);

  const distractionCount = (activeSession && latestDetection?.metrics)
    ? latestDetection.metrics.distraction_count
    : (currentSession ? (currentSession.distractionCount ?? 0) : 0);

  // Formatted displayed metrics — NEVER static Figma defaults
  const displayedFocused = currentSession ? formatDurationHMS(focusedSeconds) : '00:00:00';
  const displayedDistracted = currentSession ? formatDurationHMS(distractedSeconds) : '00:00:00';
  const displayedAway = currentSession ? formatDurationHMS(awaySeconds) : '00:00:00';
  const displayedStudyTime = currentSession ? formatDurationReadable(studyTimeSeconds) : '0m';
  const displayedFocusScore = focusScoreVal !== null ? `${Math.round(focusScoreVal)}%` : '--';
  const displayedDistractions = distractionCount;

  // Time management donut stats
  const studyTimeNote = activeSession
    ? 'Active study session'
    : currentSession
    ? 'Latest session duration'
    : 'No sessions yet';
  const focusedPercent = studyTimeSeconds > 0 ? Math.round((focusedSeconds / studyTimeSeconds) * 100) : 0;
  const distractedPercent = studyTimeSeconds > 0 ? Math.round((distractedSeconds / studyTimeSeconds) * 100) : 0;
  const displayedFocusedDonut = `${formatDurationReadable(focusedSeconds)} (${focusedPercent}%)`;
  const displayedDistractedDonut = `${formatDurationReadable(distractedSeconds)} (${distractedPercent}%)`;
  const focusedCircumference = 88;
  const focusedDashoffset = Math.max(0, focusedCircumference - (focusedCircumference * Math.min(100, focusedPercent)) / 100);
  const distractedCircumference = 88;
  const distractedDashoffset = Math.max(0, distractedCircumference - (distractedCircumference * Math.min(100, distractedPercent)) / 100);

  // Truthful live badge status resolver
  const liveBadge = resolveLiveBadgeStatus(isLive, liveState, latestDetection);

  // Dynamic subheading for live focus assistant
  const resolveAssistantSubheading = (): string => {
    if (!activeSession) {
      return 'Real-time focus detection · Start a study session first';
    }
    if (!isLive) {
      if (liveState === 'starting_camera') return 'Accessing camera hardware...';
      if (liveState === 'connecting') return 'Connecting live detection transport...';
      if (liveState === 'permission_denied') return 'Camera permission denied · Please allow access';
      if (liveState === 'camera_unavailable') return 'Camera hardware unavailable';
      if (liveState === 'connection_error') return 'Transport connection error';
      if (liveState === 'disconnected') return 'Live transport disconnected';
      return 'Real-time focus detection · Ready to monitor';
    }

    if (!latestDetection || latestDetection.state === 'calibrating') {
      const collected = latestDetection?.calibration?.samples_collected ?? 0;
      const required = latestDetection?.calibration?.required_samples ?? 30;
      return `Calibrating baseline posture (${collected}/${required} samples)...`;
    }

    if ((latestDetection.state as string) === 'detector_error') {
      return 'Detector runtime error encountered';
    }

    if (latestDetection.state === 'distracted') {
      return 'Distraction detected — please refocus';
    }

    if (latestDetection.state === 'away') {
      return 'Student is away from desk';
    }

    if (latestDetection.state === 'focused') {
      return 'Maintaining focus — posture & gaze normal';
    }

    return 'Real-time focus detection';
  };

  const handleStudySessionClick = async () => {
    alertSoundManager.initOnUserGesture();
    if (!isAuthenticated) {
      setAuthNotice(true);
      return;
    }
    setAuthNotice(false);

    try {
      if (activeSession) {
        await stopSession();
      } else {
        await startSession();
      }
    } catch {
      // Error is stored in SessionContext.sessionError
    }
  };

  const handleLiveSessionClick = async () => {
    alertSoundManager.initOnUserGesture();
    if (!activeSession) {
      setLiveNotice('Please start a Study Session first before beginning live camera monitoring.');
      return;
    }
    setLiveNotice(null);

    if (isLive || liveState === 'connected') {
      stopLiveSession();
    } else {
      await startLiveSession();
    }
  };

  const avatarInitial = user?.displayName ? user.displayName.charAt(0).toUpperCase() : 'N';
  const firstName = user?.displayName ? user.displayName.split(' ')[0] : 'Saurabh';

  return (
    <div className="sfm-page sfm-home-page" id="home-dashboard-page">
      {/* Backend Unavailable Banner */}
      {isBackendUnavailable && (
        <div className="sfm-account-banner sfm-account-banner-offline" role="alert">
          <span>
            ⚠️ <strong>Backend Offline:</strong> Cannot reach backend service at <code>http://localhost:8000</code>. Study session lifecycle actions are temporarily unavailable.
          </span>
          <button type="button" className="sfm-btn-retry" onClick={refreshActiveSession}>
            Retry Connection
          </button>
        </div>
      )}

      {/* Auth Notice Banner */}
      {authNotice && !isAuthenticated && (
        <div className="sfm-account-banner sfm-account-banner-offline" role="alert">
          <span>
            🔒 <strong>Authentication Required:</strong> Please sign in with your student account to start persistent study sessions.
          </span>
          <button type="button" className="sfm-btn-retry" onClick={() => setAuthNotice(false)}>
            Dismiss
          </button>
        </div>
      )}

      {/* Live Notice Banner (e.g. Study Session required first) */}
      {liveNotice && (
        <div className="sfm-account-banner sfm-account-banner-offline" role="alert" id="live-session-notice-banner">
          <span>
            ⚠️ <strong>Live Monitoring Notice:</strong> {liveNotice}
          </span>
          <button type="button" className="sfm-btn-retry" onClick={() => setLiveNotice(null)}>
            Dismiss
          </button>
        </div>
      )}

      {/* Live Error Banner */}
      {liveError && (
        <div className="sfm-account-banner sfm-account-banner-offline" role="alert" id="live-session-error-banner">
          <span>
            📷 <strong>Camera / Transport Notice:</strong> {liveError}
          </span>
          <button type="button" className="sfm-btn-retry" onClick={clearLiveError}>
            Dismiss
          </button>
        </div>
      )}

      {/* Session Error Banner */}
      {sessionError && (
        <div className="sfm-account-banner sfm-account-banner-offline" role="alert">
          <span>⚠️ {sessionError}</span>
          <button type="button" className="sfm-btn-retry" onClick={clearSessionError}>
            Dismiss
          </button>
        </div>
      )}

      {/* Page Header */}
      <header className="sfm-page-header">
        <div className="sfm-header-left">
          <div className="sfm-avatar-circle" aria-label="User Avatar">
            <span>{avatarInitial}</span>
          </div>
          <div className="sfm-header-titles">
            <h1 className="sfm-page-title">{data.greetingTitle}</h1>
            <p className="sfm-page-subtitle">{data.greetingSubtitle}</p>
          </div>
        </div>

        <div className="sfm-header-right">
          {/* Mascot & Prompt bubble */}
          <div className="sfm-mascot-group">
            <div className="sfm-mascot-icon">
              <MascotBotIcon size={38} />
            </div>
            <div className="sfm-speech-bubble">
              <span>Need a boost,</span>
              <span>{firstName}?</span>
            </div>
          </div>

          {/* Primary Action Button */}
          <button
            type="button"
            className={`sfm-btn-primary ${activeSession ? 'is-active-session' : ''}`}
            onClick={handleStudySessionClick}
            disabled={isStarting || isStopping || isBackendUnavailable}
            id="btn-start-study-session"
          >
            <span>
              {isStarting
                ? 'Starting...'
                : isStopping
                ? 'Ending...'
                : activeSession
                ? 'End Study Session'
                : 'Start Study Session'}
            </span>
            <span className="sfm-shortcut-pill">S</span>
          </button>

          {/* Export Action */}
          <button
            type="button"
            className="sfm-icon-btn"
            aria-label="Export or share dashboard"
            title="Export summary"
          >
            <ExportCloverIcon size={18} />
          </button>
        </div>
      </header>

      {/* Active Study Session Lifecycle Card */}
      {activeSession && (
        <div className="sfm-card sfm-card-full sfm-session-lifecycle-card" id="active-study-session-card">
          <div className="sfm-lifecycle-left">
            <span className="sfm-lifecycle-pulse-dot" />
            <div className="sfm-lifecycle-info">
              <div className="sfm-lifecycle-title-row">
                <span className="sfm-lifecycle-title">Active Study Session</span>
                <span className="sfm-session-id-pill" id="active-session-id-pill" title={`Session ID: ${activeSession.id}`}>
                  #{activeSession.id.slice(0, 8)}
                </span>
                <span className="sfm-lifecycle-status-badge" id="active-session-status-badge">active</span>
              </div>
              <p className="sfm-lifecycle-meta">
                Started at {new Date(activeSession.startedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} • Container for live camera monitoring
              </p>
            </div>
          </div>
          <div className="sfm-lifecycle-right">
            <div className="sfm-lifecycle-timer-box">
              <span className="sfm-lifecycle-timer-label">SESSION TIME</span>
              <span className="sfm-lifecycle-timer-val" id="active-session-elapsed-timer">{formatTimer(elapsedSeconds)}</span>
            </div>
            <button
              type="button"
              className="sfm-btn-lifecycle-stop"
              id="btn-stop-session-card"
              onClick={handleStudySessionClick}
              disabled={isStopping}
            >
              {isStopping ? 'Ending...' : 'End Session'}
            </button>
          </div>
        </div>
      )}

      {/* Main Grid Content */}
      <div className="sfm-content-grid">
        {/* Card 1: Live Focus Assistant */}
        <section
          className="sfm-card sfm-card-full sfm-live-assistant-card"
          aria-labelledby="live-assistant-heading"
        >
          {/* Left Preview Box */}
          <div className="sfm-video-preview-box">
            <div
              className={`sfm-live-indicator ${liveBadge.indicatorClass}`}
              id="live-transport-indicator"
            >
              <span className={`sfm-live-dot ${liveBadge.isPulsing ? 'is-pulsing' : ''}`}>●</span>
              <span className="sfm-live-text" id="live-transport-status-text">
                {liveBadge.text}
              </span>
            </div>
            <div className="sfm-mock-camera-frame" id="live-camera-preview-container">
              <video
                ref={videoRef}
                id="live-camera-video-preview"
                autoPlay
                playsInline
                muted
                className={`sfm-camera-video-preview ${isLive || liveState === 'camera_ready' ? 'is-visible' : 'is-hidden'}`}
              />
              {!(isLive || liveState === 'camera_ready') && (
                <div className="sfm-frame-inner"></div>
              )}
            </div>
          </div>

          {/* Center Info & Control */}
          <div className="sfm-live-assistant-info">
            <h2 id="live-assistant-heading" className="sfm-card-heading">
              Live Focus Assistant
            </h2>
            <p className="sfm-card-subheading">{resolveAssistantSubheading()}</p>
            <button
              type="button"
              className={`sfm-btn-live-session ${isLive ? 'is-live-active' : ''}`}
              id="btn-start-live-session"
              onClick={handleLiveSessionClick}
              disabled={liveState === 'starting_camera' || liveState === 'connecting' || liveState === 'stopping'}
              title={isLive ? 'Stop Live Camera Transport' : 'Start Live Camera Transport'}
            >
              {isLive ? (
                <span className="sfm-stop-icon-box">■</span>
              ) : (
                <PlayIcon size={12} color="#FFFFFF" />
              )}
              <span>
                {liveState === 'starting_camera'
                  ? 'Starting Camera...'
                  : liveState === 'connecting'
                  ? 'Connecting...'
                  : liveState === 'stopping'
                  ? 'Stopping...'
                  : isLive
                  ? 'Stop Live Session'
                  : 'Start Live Session'}
              </span>
            </button>

            {/* Contained Active Alerts / Details */}
            {isLive && latestDetection && (
              <div className="sfm-live-alert-container" id="live-active-alerts-container">
                {latestDetection.state === 'distracted' && (
                  <>
                    <div className="sfm-live-alert-header">
                      <span className="sfm-alert-badge is-distracted" id="live-alert-badge-distracted">
                        ⚠️ DISTRACTED
                      </span>
                    </div>
                    {latestDetection.active_detections && latestDetection.active_detections.length > 0 ? (
                      <div className="sfm-alert-chips" id="live-alert-chips-list">
                        {latestDetection.active_detections.map((det, idx) => (
                          <span
                            key={`${det.category}-${idx}`}
                            className="sfm-alert-chip"
                            id={`alert-chip-${det.category}`}
                          >
                            <span>{getDetectorCategoryLabel(det.category, det.alert_name)}</span>
                            <span className="sfm-alert-chip-duration">
                              {`(${formatAlertDuration(det.duration_seconds)})`}
                            </span>
                          </span>
                        ))}
                      </div>
                    ) : (
                      <div className="sfm-alert-chips">
                        <span className="sfm-alert-chip">
                          <span>Distraction Active</span>
                        </span>
                      </div>
                    )}
                  </>
                )}

                {latestDetection.state === 'away' && (
                  <div className="sfm-live-alert-header">
                    <span className="sfm-alert-badge is-away" id="live-alert-badge-away">
                      🏃 AWAY FROM DESK
                    </span>
                  </div>
                )}

                {latestDetection.state === 'calibrating' && (
                  <div className="sfm-live-alert-header">
                    <span className="sfm-alert-badge is-calibrating" id="live-alert-badge-calibrating">
                      {`🎯 CALIBRATING (${latestDetection.calibration?.samples_collected ?? 0}/${latestDetection.calibration?.required_samples ?? 30})`}
                    </span>
                  </div>
                )}

                {latestDetection.state === 'focused' && (
                  <div className="sfm-live-alert-header">
                    <span className="sfm-alert-badge is-focused" id="live-alert-badge-focused">
                      ✓ FOCUSED
                    </span>
                  </div>
                )}

                {(latestDetection.state as string) === 'detector_error' && (
                  <div className="sfm-live-alert-header">
                    <span className="sfm-alert-badge is-error" id="live-alert-badge-error">
                      ⚠️ DETECTOR ERROR
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right Live Stats */}
          <div className="sfm-live-stats-list">
            <div className="sfm-stat-row">
              <div className="sfm-stat-label">
                <TargetFocusIcon size={15} color="#171A24" />
                <span>Focused</span>
              </div>
              <span className="sfm-stat-value" id="live-metric-focused">{displayedFocused}</span>
            </div>

            <div className="sfm-stat-divider" />

            <div className="sfm-stat-row">
              <div className="sfm-stat-label">
                <AlertTriangleIcon size={15} color="#171A24" />
                <span>Distracted</span>
              </div>
              <span className="sfm-stat-value" id="live-metric-distracted">{displayedDistracted}</span>
            </div>

            <div className="sfm-stat-divider" />

            <div className="sfm-stat-row">
              <div className="sfm-stat-label">
                <AwayCircleIcon size={15} color="#171A24" />
                <span>Away</span>
              </div>
              <span className="sfm-stat-value" id="live-metric-away">{displayedAway}</span>
            </div>
          </div>
        </section>

        {/* 3 Metric Cards Row */}
        <div className="sfm-metrics-row">
          {/* Metric 1: Focus Score */}
          <section className="sfm-card sfm-metric-card" aria-label="Focus Score">
            <div className="sfm-metric-card-header">
              <h3 className="sfm-metric-title">Focus Score</h3>
              <div className="sfm-badge-lavender" aria-hidden="true">
                <LightningIcon size={13} color="#171A24" />
              </div>
            </div>

            <div className="sfm-sparkline-container" aria-hidden="true">
              <svg
                width="100%"
                height="48"
                viewBox="0 0 240 60"
                preserveAspectRatio="none"
              >
                {focusScoreVal !== null ? (
                  <>
                    <line
                      x1="10"
                      y1={Math.max(10, Math.min(50, 60 - focusScoreVal * 0.5))}
                      x2="230"
                      y2={Math.max(10, Math.min(50, 60 - focusScoreVal * 0.5))}
                      stroke="#75A564"
                      strokeWidth="2.2"
                      strokeLinecap="round"
                    />
                    <circle
                      cx="10"
                      cy={Math.max(10, Math.min(50, 60 - focusScoreVal * 0.5))}
                      r="3"
                      fill="#75A564"
                    />
                    <circle
                      cx="230"
                      cy={Math.max(10, Math.min(50, 60 - focusScoreVal * 0.5))}
                      r="3"
                      fill="#75A564"
                    />
                  </>
                ) : (
                  <line
                    x1="10"
                    y1="30"
                    x2="230"
                    y2="30"
                    stroke="#D1D5DB"
                    strokeWidth="1.5"
                    strokeDasharray="4 4"
                  />
                )}
              </svg>
            </div>

            <div className="sfm-metric-footer">
              <div className="sfm-big-metric" id="card-metric-focus-score">{displayedFocusScore}</div>
              <div className="sfm-metric-change">
                {currentSession ? (activeSession ? 'Live calculation' : 'Session score') : 'No session data'}
              </div>
            </div>
          </section>

          {/* Metric 2: Time Management */}
          <section className="sfm-card sfm-metric-card" aria-label="Time Management">
            <div className="sfm-metric-card-header">
              <h3 className="sfm-metric-title">Time Management</h3>
              <div className="sfm-badge-lavender" aria-hidden="true">
                <ClockTimeIcon size={13} color="#171A24" />
              </div>
            </div>

            <div className="sfm-time-management-body">
              <span className="sfm-metric-sublabel">
                Study Time
              </span>
              <div className="sfm-big-metric sfm-time-value" id="card-metric-study-time">
                {displayedStudyTime}
              </div>
              <span className="sfm-metric-note">{studyTimeNote}</span>
            </div>

            <div className="sfm-donut-row">
              {/* Focused Time Donut */}
              <div className="sfm-donut-item">
                <svg className="sfm-donut-ring" width="34" height="34" viewBox="0 0 36 36">
                  <circle
                    cx="18"
                    cy="18"
                    r="14"
                    fill="none"
                    stroke="#E6E8EB"
                    strokeWidth="4"
                  />
                  <circle
                    cx="18"
                    cy="18"
                    r="14"
                    fill="none"
                    stroke="#65E815"
                    strokeWidth="4.5"
                    strokeDasharray="88 88"
                    strokeDashoffset={focusedDashoffset}
                    strokeLinecap="round"
                  />
                </svg>
                <div className="sfm-donut-text">
                  <span className="sfm-donut-label">
                    {data.timeManagement.focusedLabel}
                  </span>
                  <span className="sfm-donut-val">
                    {displayedFocusedDonut}
                  </span>
                </div>
              </div>

              {/* Distracted Time Donut */}
              <div className="sfm-donut-item">
                <svg className="sfm-donut-ring" width="34" height="34" viewBox="0 0 36 36">
                  <circle
                    cx="18"
                    cy="18"
                    r="14"
                    fill="none"
                    stroke="#E6E8EB"
                    strokeWidth="4"
                  />
                  <circle
                    cx="18"
                    cy="18"
                    r="14"
                    fill="none"
                    stroke="#FF4C4F"
                    strokeWidth="4.5"
                    strokeDasharray="88 88"
                    strokeDashoffset={distractedDashoffset}
                    strokeLinecap="round"
                  />
                </svg>
                <div className="sfm-donut-text">
                  <span className="sfm-donut-label">
                    {data.timeManagement.distractedLabel}
                  </span>
                  <span className="sfm-donut-val">
                    {displayedDistractedDonut}
                  </span>
                </div>
              </div>
            </div>
          </section>

          {/* Metric 3: Interaction Activity */}
          <section className="sfm-card sfm-metric-card" aria-label="Interaction Activity">
            <div className="sfm-metric-card-header">
              <h3 className="sfm-metric-title">Interaction Activity</h3>
            </div>

            <div className="sfm-interaction-body">
              <span className="sfm-metric-sublabel">
                {data.interactionActivity.subtitle}
              </span>
              <div className="sfm-big-metric sfm-activity-value" id="card-metric-distractions">
                {displayedDistractions}
              </div>
              <span className="sfm-metric-note">
                {activeSession ? 'Current session' : currentSession ? 'Session total' : data.interactionActivity.todayLabel}
              </span>
            </div>

            {/* Blue Activity Bars */}
            <div className="sfm-activity-bars" aria-hidden="true">
              {[0, 1, 2, 3, 4, 5, 6, 7, 8].map((barIdx) => {
                const heightPercent =
                  distractionCount > 0
                    ? Math.min(100, Math.max(15, distractionCount * 12 + ((barIdx * 7) % 25)))
                    : 15;
                return (
                  <div
                    key={barIdx}
                    className="sfm-activity-bar"
                    style={{ height: `${heightPercent}%`, opacity: distractionCount > 0 ? 1 : 0.4 }}
                  />
                );
              })}
            </div>
          </section>
        </div>

        {/* Card 3: Focus Timeline */}
        <section
          className="sfm-card sfm-card-full sfm-timeline-card"
          aria-labelledby="focus-timeline-heading"
        >
          <div className="sfm-timeline-header">
            <h2 id="focus-timeline-heading" className="sfm-card-heading">
              Focus Timeline
            </h2>

            <div className="sfm-timeline-legend">
              <div className="sfm-legend-item">
                <span className="sfm-legend-dot is-focused" />
                <span>Focused</span>
              </div>
              <div className="sfm-legend-item">
                <span className="sfm-legend-dot is-distracted" />
                <span>Distracted</span>
              </div>
              <div className="sfm-legend-item">
                <span className="sfm-legend-dot is-away" />
                <span>Away</span>
              </div>
            </div>
          </div>

          {/* Timeline Graphical Bar */}
          <div className="sfm-timeline-track" aria-label="Visual Focus Timeline">
            {timelineVM.isEmpty ? (
              <div className="sfm-timeline-empty" id="focus-timeline-empty-track">
                <span>No active session timeline yet. Start a study session to track focus progression.</span>
              </div>
            ) : (
              <div className="sfm-timeline-segments" id="focus-timeline-segments-track">
                {timelineVM.segments.map((seg, idx) => (
                  <React.Fragment key={seg.id || idx}>
                    {idx > 0 && <div className="sfm-segment-gap" style={{ flex: 1 }} />}
                    <div
                      className={`sfm-segment sfm-segment-${seg.state}`}
                      style={{
                        flex: Math.max(
                          1,
                          Math.round((seg.durationSeconds / Math.max(1, timelineVM.totalSeconds)) * 100)
                        ),
                      }}
                      title={`${seg.state.charAt(0).toUpperCase() + seg.state.slice(1)}: ${Math.round(seg.durationSeconds)}s`}
                    />
                  </React.Fragment>
                ))}
              </div>
            )}

            {/* Time labels below bar */}
            <div className="sfm-timeline-labels">
              {timelineVM.timeMarks.map((mark, idx) => (
                <span key={idx} className="sfm-time-tick">
                  {mark}
                </span>
              ))}
            </div>
          </div>

          {/* Grid note footer */}
          <div className="sfm-timeline-footer-note">
            <span>
              {activeSession
                ? 'Session Timeline: Real-time focus progression · Updates dynamically during live monitoring'
                : 'Focus progression will be recorded when an active study session is monitored'}
            </span>
          </div>
        </section>
      </div>
    </div>
  );
};
