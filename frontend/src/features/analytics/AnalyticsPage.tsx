import React from 'react';
import { AnalyticsPageData } from '../../types/dashboard';
import { ExportCloverIcon } from '../../components/common/Icons';

interface AnalyticsPageProps {
  data: AnalyticsPageData;
}

export const AnalyticsPage: React.FC<AnalyticsPageProps> = ({ data }) => {
  return (
    <div className="sfm-page sfm-analytics-page" id="analytics-page">
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
          <button type="button" className="sfm-btn-primary" id="btn-analytics-study-session">
            <span>Start Study Session</span>
            <span className="sfm-shortcut-pill">S</span>
          </button>

          <button
            type="button"
            className="sfm-icon-btn"
            aria-label="Export analytics report"
            title="Export analytics"
          >
            <ExportCloverIcon size={18} />
          </button>
        </div>
      </header>

      {/* Grid Content */}
      <div className="sfm-content-grid">
        {/* Card 1: Focus Score Trend */}
        <section
          className="sfm-card sfm-card-full sfm-trend-card"
          aria-labelledby="trend-heading"
        >
          <div className="sfm-trend-header">
            <div className="sfm-trend-titles">
              <h2 id="trend-heading" className="sfm-card-heading">
                {data.trend.title}
              </h2>
              <p className="sfm-card-subheading">{data.trend.subtitle}</p>
            </div>

            <div className="sfm-trend-stats">
              <span className="sfm-badge-pill">{data.trend.badgeText}</span>
              <div className="sfm-trend-metric-group">
                <span className="sfm-trend-score">{data.trend.score}</span>
                <span className="sfm-trend-change">{data.trend.changeText}</span>
              </div>
            </div>
          </div>

          {/* SVG Trend Graph */}
          <div className="sfm-trend-graph-container" aria-label="Weekly focus trend line chart">
            <svg
              className="sfm-trend-svg"
              viewBox="0 0 920 180"
              preserveAspectRatio="none"
            >
              {/* Trend line segments */}
              {data.trend.trendLines.map((seg, idx) => (
                <g key={idx}>
                  <line
                    x1={seg.x1}
                    y1={seg.y1}
                    x2={seg.x2}
                    y2={seg.y2}
                    stroke="#9787BF"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                  />
                  {seg.startPoint && (
                    <circle cx={seg.x1} cy={seg.y1} r="3" fill="#9787BF" />
                  )}
                  {seg.endPoint && (
                    <circle cx={seg.x2} cy={seg.y2} r="3" fill="#9787BF" />
                  )}
                </g>
              ))}

              {/* Extra dots matching screenshot */}
              <circle cx="180" cy="58" r="3" fill="#9787BF" />
              <circle cx="320" cy="72" r="3" fill="#9787BF" />
              <circle cx="460" cy="52" r="3" fill="#9787BF" />
              <circle cx="600" cy="38" r="3" fill="#9787BF" />
              <circle cx="740" cy="50" r="3" fill="#9787BF" />
              <circle cx="880" cy="58" r="3" fill="#9787BF" />

              {/* Baseline divider line above day labels */}
              <line
                x1="20"
                y1="145"
                x2="900"
                y2="145"
                stroke="#E5E7EB"
                strokeWidth="1"
              />
            </svg>

            {/* Day labels below baseline */}
            <div className="sfm-trend-days">
              {data.trend.days.map((day) => (
                <span key={day} className="sfm-day-label">
                  {day}
                </span>
              ))}
            </div>
          </div>
        </section>

        {/* 2-Column Row: Breakdown & Comparison */}
        <div className="sfm-two-col-row">
          {/* Card 2: Distraction Breakdown */}
          <section
            className="sfm-card sfm-col-card sfm-breakdown-card"
            aria-labelledby="breakdown-heading"
          >
            <h2 id="breakdown-heading" className="sfm-card-heading">
              {data.breakdown.title}
            </h2>

            <div className="sfm-breakdown-list">
              {data.breakdown.categories.map((cat) => (
                <div key={cat.id} className="sfm-breakdown-row">
                  <span className="sfm-breakdown-label">{cat.label}</span>
                  <div className="sfm-breakdown-bar-wrap">
                    <div
                      className="sfm-breakdown-bar-fill"
                      style={{ width: `${cat.percentWidth}%` }}
                    />
                  </div>
                  <span className="sfm-breakdown-count">{cat.count}</span>
                  <span className="sfm-breakdown-duration">{cat.duration}</span>
                </div>
              ))}
            </div>

            <div className="sfm-breakdown-footer">
              <span>{data.breakdown.footerSummary}</span>
            </div>
          </section>

          {/* Card 3: Comparison */}
          <section
            className="sfm-card sfm-col-card sfm-comparison-card"
            aria-labelledby="comparison-heading"
          >
            <h2 id="comparison-heading" className="sfm-card-heading">
              {data.comparison.title}
            </h2>

            <div className="sfm-comparison-list">
              {data.comparison.rows.map((row) => (
                <div key={row.id} className="sfm-comparison-pill">
                  <span className="sfm-comparison-period">{row.period}</span>
                  <span className="sfm-comparison-score">{row.score}</span>
                  <span className="sfm-comparison-duration">{row.duration}</span>
                </div>
              ))}
            </div>

            <div className="sfm-comparison-footer">
              <span className="sfm-comparison-footer-label">Date range</span>
              <button type="button" className="sfm-btn-date-range">
                {data.comparison.dateRange}
              </button>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};
