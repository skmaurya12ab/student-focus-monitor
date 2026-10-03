import React, { useState } from 'react';
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

interface HomePageProps {
  data: HomeDashboardData;
}

export const HomePage: React.FC<HomePageProps> = ({ data }) => {
  const {
    activeSession,
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
    startLiveSession,
    stopLiveSession,
    error: liveError,
    clearError: clearLiveError,
  } = useLiveTransport();
  const [authNotice, setAuthNotice] = useState<boolean>(false);
  const [liveNotice, setLiveNotice] = useState<string | null>(null);

  const formatTimer = (totalSeconds: number): string => {
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    if (hours > 0) {
      return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  };

  const handleStudySessionClick = async () => {
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
                Started at {new Date(activeSession.startedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} • Container for upcoming live monitoring
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
            <div className={`sfm-live-indicator is-${liveState}`} id="live-transport-indicator">
              <span className={`sfm-live-dot ${isLive ? 'is-pulsing' : ''}`}>●</span>
              <span className="sfm-live-text" id="live-transport-status-text">
                {isLive
                  ? 'LIVE'
                  : liveState === 'connecting'
                  ? 'CONNECTING'
                  : liveState === 'starting_camera'
                  ? 'STARTING'
                  : 'STANDBY'}
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
            <p className="sfm-card-subheading">Real-time focus detection</p>
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
          </div>


          {/* Right Live Stats */}
          <div className="sfm-live-stats-list">
            <div className="sfm-stat-row">
              <div className="sfm-stat-label">
                <TargetFocusIcon size={15} color="#171A24" />
                <span>Focused</span>
              </div>
              <span className="sfm-stat-value">{data.liveStats.focused}</span>
            </div>

            <div className="sfm-stat-divider" />

            <div className="sfm-stat-row">
              <div className="sfm-stat-label">
                <AlertTriangleIcon size={15} color="#171A24" />
                <span>Distracted</span>
              </div>
              <span className="sfm-stat-value">{data.liveStats.distracted}</span>
            </div>

            <div className="sfm-stat-divider" />

            <div className="sfm-stat-row">
              <div className="sfm-stat-label">
                <AwayCircleIcon size={15} color="#171A24" />
                <span>Away</span>
              </div>
              <span className="sfm-stat-value">{data.liveStats.away}</span>
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
                {data.focusScore.sparklineSegments.map((seg, idx) => (
                  <g key={idx}>
                    <line
                      x1={seg.startX}
                      y1={seg.startY}
                      x2={seg.endX}
                      y2={seg.endY}
                      stroke="#75A564"
                      strokeWidth="2.2"
                      strokeLinecap="round"
                    />
                    <circle cx={seg.startX} cy={seg.startY} r="2.5" fill="#75A564" />
                    <circle cx={seg.endX} cy={seg.endY} r="2.5" fill="#75A564" />
                  </g>
                ))}
                {/* final point */}
                <circle cx="232" cy="24" r="2.5" fill="#75A564" />
              </svg>
            </div>

            <div className="sfm-metric-footer">
              <div className="sfm-big-metric">{data.focusScore.score}%</div>
              <div className="sfm-metric-change">{data.focusScore.changeText}</div>
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
                {data.timeManagement.studyTime && 'Study Time'}
              </span>
              <div className="sfm-big-metric sfm-time-value">
                {data.timeManagement.studyTime}
              </div>
              <span className="sfm-metric-note">{data.timeManagement.totalLabel}</span>
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
                    strokeDashoffset="20"
                    strokeLinecap="round"
                  />
                </svg>
                <div className="sfm-donut-text">
                  <span className="sfm-donut-label">
                    {data.timeManagement.focusedLabel}
                  </span>
                  <span className="sfm-donut-val">
                    {data.timeManagement.focusedValue}
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
                    strokeDashoffset="65"
                    strokeLinecap="round"
                  />
                </svg>
                <div className="sfm-donut-text">
                  <span className="sfm-donut-label">
                    {data.timeManagement.distractedLabel}
                  </span>
                  <span className="sfm-donut-val">
                    {data.timeManagement.distractedValue}
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
              <div className="sfm-big-metric sfm-activity-value">
                {data.interactionActivity.distractions}
              </div>
              <span className="sfm-metric-note">
                {data.interactionActivity.todayLabel}
              </span>
            </div>

            {/* Blue Activity Bars */}
            <div className="sfm-activity-bars" aria-hidden="true">
              {data.interactionActivity.bars.map((bar, idx) => (
                <div
                  key={idx}
                  className="sfm-activity-bar"
                  style={{ height: `${bar.heightPercent}%` }}
                />
              ))}
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
                <span className="sfm-legend-dot" />
                <span>Focused</span>
              </div>
              <div className="sfm-legend-item">
                <span className="sfm-legend-dot" />
                <span>Distracted</span>
              </div>
              <div className="sfm-legend-item">
                <span className="sfm-legend-dot" />
                <span>Away</span>
              </div>
            </div>
          </div>

          {/* Timeline Graphical Bar */}
          <div className="sfm-timeline-track" aria-label="Visual Focus Timeline">
            <div className="sfm-timeline-segments">
              {/* Segment 1: Green 10:00 - ~10:28 */}
              <div
                className="sfm-segment sfm-segment-focused"
                style={{ flex: 26 }}
                title="Focused: 10:00 AM - 10:28 AM"
              />
              <div className="sfm-segment-gap" style={{ flex: 1 }} />
              {/* Segment 2: Green 10:30 - ~10:48 */}
              <div
                className="sfm-segment sfm-segment-focused"
                style={{ flex: 25 }}
                title="Focused: 10:30 AM - 10:48 AM"
              />
              <div className="sfm-segment-gap" style={{ flex: 1 }} />
              {/* Segment 3: Red 10:49 - 10:56 */}
              <div
                className="sfm-segment sfm-segment-distracted"
                style={{ flex: 9 }}
                title="Distracted: 10:49 AM - 10:56 AM"
              />
              <div className="sfm-segment-gap" style={{ flex: 1 }} />
              {/* Segment 4: Green 10:57 - 11:27 */}
              <div
                className="sfm-segment sfm-segment-focused"
                style={{ flex: 34 }}
                title="Focused: 10:57 AM - 11:27 AM"
              />
              <div className="sfm-segment-gap" style={{ flex: 1 }} />
              {/* Segment 5: Red 11:28 - 11:37 */}
              <div
                className="sfm-segment sfm-segment-distracted"
                style={{ flex: 10 }}
                title="Distracted: 11:28 AM - 11:37 AM"
              />
              <div className="sfm-segment-gap" style={{ flex: 1 }} />
              {/* Segment 6: Green 11:38 - 12:00 */}
              <div
                className="sfm-segment sfm-segment-focused"
                style={{ flex: 27 }}
                title="Focused: 11:38 AM - 12:00 PM"
              />
              <div className="sfm-segment-gap" style={{ flex: 1 }} />
              {/* Segment 7: Red 12:01 - 12:08 */}
              <div
                className="sfm-segment sfm-segment-distracted"
                style={{ flex: 8 }}
                title="Distracted: 12:01 PM - 12:08 PM"
              />
              <div className="sfm-segment-gap" style={{ flex: 1 }} />
              {/* Segment 8: Green 12:09 - 12:35 */}
              <div
                className="sfm-segment sfm-segment-focused"
                style={{ flex: 36 }}
                title="Focused: 12:09 PM - 12:35 PM"
              />
              <div className="sfm-segment-gap" style={{ flex: 1 }} />
              {/* Segment 9: Red 12:36 - 12:41 */}
              <div
                className="sfm-segment sfm-segment-distracted"
                style={{ flex: 6 }}
                title="Distracted: 12:36 PM - 12:41 PM"
              />
              <div className="sfm-segment-gap" style={{ flex: 1 }} />
              {/* Segment 10: Green 12:42 - 12:58 */}
              <div
                className="sfm-segment sfm-segment-focused"
                style={{ flex: 30 }}
                title="Focused: 12:42 PM - 12:58 PM"
              />
            </div>

            {/* Time labels below bar */}
            <div className="sfm-timeline-labels">
              {data.focusTimeline.timeMarks.map((mark, idx) => (
                <span key={idx} className="sfm-time-tick">
                  {mark}
                </span>
              ))}
            </div>
          </div>

          {/* Grid note footer */}
          <div className="sfm-timeline-footer-note">
            <span>{data.focusTimeline.footerNote}</span>
          </div>
        </section>
      </div>
    </div>
  );
};
