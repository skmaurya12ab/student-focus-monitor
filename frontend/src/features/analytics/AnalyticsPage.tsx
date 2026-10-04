import React, { useState, useEffect, useCallback } from 'react';
import { AnalyticsData } from '../../types/analytics';
import { fetchAnalytics } from '../../services/analyticsApi';
import { ExportCloverIcon } from '../../components/common/Icons';

export interface AnalyticsPageProps {
  initialData?: AnalyticsData;
}

export const AnalyticsPage: React.FC<AnalyticsPageProps> = ({ initialData }) => {
  const [range, setRange] = useState<'7d' | '30d' | 'all'>('7d');
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(initialData || null);
  const [isLoading, setIsLoading] = useState<boolean>(initialData === undefined);
  const [error, setError] = useState<string | null>(null);

  const loadAnalytics = useCallback(async (selectedRange: '7d' | '30d' | 'all') => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchAnalytics(selectedRange);
      setAnalytics(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load focus analytics');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (initialData !== undefined) return;
    loadAnalytics(range);
  }, [loadAnalytics, range, initialData]);

  const handleStartStudySession = () => {
    const startBtn = document.getElementById('btn-start-study-session');
    if (startBtn) {
      startBtn.click();
    } else {
      window.location.pathname = '/';
    }
  };

  const hasData = analytics && analytics.summary.completedSessionsCount > 0;

  return (
    <div className="sfm-page sfm-analytics-page" id="analytics-page">
      {/* Header */}
      <header className="sfm-page-header">
        <div className="sfm-header-left">
          <div className="sfm-avatar-circle" aria-label="User Avatar">
            <span>A</span>
          </div>
          <div className="sfm-header-titles">
            <h1 className="sfm-page-title">Focus Analytics</h1>
            <p className="sfm-page-subtitle">Understand your attention patterns over time.</p>
          </div>
        </div>

        <div className="sfm-header-right">
          {/* Range Selector Controls */}
          <div className="sfm-range-selector-group" role="group" aria-label="Analytics date range filter">
            <button
              type="button"
              className={`sfm-range-pill ${range === '7d' ? 'is-active' : ''}`}
              id="btn-range-7d"
              onClick={() => setRange('7d')}
            >
              7 Days
            </button>
            <button
              type="button"
              className={`sfm-range-pill ${range === '30d' ? 'is-active' : ''}`}
              id="btn-range-30d"
              onClick={() => setRange('30d')}
            >
              30 Days
            </button>
            <button
              type="button"
              className={`sfm-range-pill ${range === 'all' ? 'is-active' : ''}`}
              id="btn-range-all"
              onClick={() => setRange('all')}
            >
              All Time
            </button>
          </div>

          <button
            type="button"
            className="sfm-btn-primary"
            id="btn-analytics-study-session"
            onClick={handleStartStudySession}
          >
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

      {/* Main Content */}
      <div className="sfm-content-grid">
        {isLoading ? (
          <section className="sfm-card sfm-card-full">
            <div className="sfm-empty-state-box" id="analytics-loading-state">
              <p className="sfm-empty-state-title">Loading analytics...</p>
              <p className="sfm-empty-state-desc">Aggregating historical performance metrics.</p>
            </div>
          </section>
        ) : error ? (
          <section className="sfm-card sfm-card-full">
            <div className="sfm-empty-state-box" id="analytics-error-state">
              <p className="sfm-empty-state-title">Error loading analytics</p>
              <p className="sfm-empty-state-desc">{error}</p>
            </div>
          </section>
        ) : !hasData ? (
          <section className="sfm-card sfm-card-full">
            <div className="sfm-empty-state-box" id="analytics-empty-state">
              <p className="sfm-empty-state-title">No analytics available yet.</p>
              <p className="sfm-empty-state-desc">
                Complete study sessions to generate focus trends, distraction breakdowns, and historical insights.
              </p>
            </div>
          </section>
        ) : (
          <>
            {/* Card 1: Focus Score Trend */}
            <section
              className="sfm-card sfm-card-full sfm-trend-card"
              id="focus-score-trend-card"
              aria-labelledby="trend-heading"
            >
              <div className="sfm-trend-header">
                <div className="sfm-trend-titles">
                  <h2 id="trend-heading" className="sfm-card-heading">
                    {analytics.trend.title}
                  </h2>
                  <p className="sfm-card-subheading">{analytics.trend.subtitle}</p>
                </div>

                <div className="sfm-trend-stats">
                  <span className="sfm-badge-pill">{analytics.trend.badgeText}</span>
                  <div className="sfm-trend-metric-group">
                    <span className="sfm-trend-score">{analytics.trend.score}</span>
                    {analytics.trend.changeText && (
                      <span className="sfm-trend-change">{analytics.trend.changeText}</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Dynamic SVG Trend Graph */}
              <div className="sfm-trend-graph-container" aria-label="Focus score trend line chart">
                <svg
                  className="sfm-trend-svg"
                  viewBox="0 0 920 180"
                  preserveAspectRatio="none"
                >
                  {/* Baseline divider line above day labels */}
                  <line
                    x1="20"
                    y1="145"
                    x2="900"
                    y2="145"
                    stroke="#E5E7EB"
                    strokeWidth="1"
                  />

                  {/* Dynamic Trend Line Segments */}
                  {analytics.trend.trendLines.map((seg, idx) => (
                    <line
                      key={idx}
                      x1={seg.x1}
                      y1={seg.y1}
                      x2={seg.x2}
                      y2={seg.y2}
                      stroke="#9787BF"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                    />
                  ))}

                  {/* Scored Data Points */}
                  {analytics.trend.points.map((pt, idx) => (
                    <circle
                      key={idx}
                      cx={pt.cx}
                      cy={pt.cy}
                      r="4"
                      fill="#9787BF"
                    >
                      <title>{`${pt.day} (${pt.date}): ${Math.round(pt.score)}% focus`}</title>
                    </circle>
                  ))}
                </svg>

                {/* Day labels below baseline */}
                <div className="sfm-trend-days">
                  {analytics.trend.days.map((day, idx) => (
                    <span key={idx} className="sfm-day-label">
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
                id="distraction-breakdown-card"
                aria-labelledby="breakdown-heading"
              >
                <h2 id="breakdown-heading" className="sfm-card-heading">
                  {analytics.breakdown.title}
                </h2>

                <div className="sfm-breakdown-list">
                  {analytics.breakdown.categories.map((cat) => (
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
                  <span>{analytics.breakdown.footerSummary}</span>
                </div>
              </section>

              {/* Card 3: Comparison */}
              <section
                className="sfm-card sfm-col-card sfm-comparison-card"
                id="performance-comparison-card"
                aria-labelledby="comparison-heading"
              >
                <h2 id="comparison-heading" className="sfm-card-heading">
                  {analytics.comparison.title}
                </h2>

                <div className="sfm-comparison-list">
                  {analytics.comparison.rows.map((row) => (
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
                    {analytics.comparison.dateRange}
                  </button>
                </div>
              </section>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
