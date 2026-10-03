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

interface HomePageProps {
  data: HomeDashboardData;
}

export const HomePage: React.FC<HomePageProps> = ({ data }) => {
  const [isSessionActive, setIsSessionActive] = useState<boolean>(false);

  const toggleSession = () => {
    setIsSessionActive((prev) => !prev);
  };

  return (
    <div className="sfm-page sfm-home-page" id="home-dashboard-page">
      {/* Page Header */}
      <header className="sfm-page-header">
        <div className="sfm-header-left">
          <div className="sfm-avatar-circle" aria-label="User Avatar">
            <span>N</span>
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
              <span>Saurabh?</span>
            </div>
          </div>

          {/* Primary Action Button */}
          <button
            type="button"
            className="sfm-btn-primary"
            onClick={toggleSession}
            id="btn-start-study-session"
          >
            <span>{isSessionActive ? 'End Study Session' : 'Start Study Session'}</span>
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

      {/* Main Grid Content */}
      <div className="sfm-content-grid">
        {/* Card 1: Live Focus Assistant */}
        <section
          className="sfm-card sfm-card-full sfm-live-assistant-card"
          aria-labelledby="live-assistant-heading"
        >
          {/* Left Preview Box */}
          <div className="sfm-video-preview-box">
            <div className="sfm-live-indicator">
              <span className="sfm-live-dot">●</span>
              <span className="sfm-live-text">{data.liveStatus}</span>
            </div>
            <div className="sfm-mock-camera-frame">
              <div className="sfm-frame-inner"></div>
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
              className="sfm-btn-live-session"
              onClick={toggleSession}
              id="btn-start-live-session"
            >
              <PlayIcon size={12} color="#FFFFFF" />
              <span>{isSessionActive ? 'Stop Live Session' : 'Start Live Session'}</span>
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
