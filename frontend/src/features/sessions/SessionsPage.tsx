import React, { useState } from 'react';
import { SessionsHistoryData, SessionRowData } from '../../types/dashboard';
import {
  SearchIcon,
  ChevronDownIcon,
  ExportCloverIcon,
} from '../../components/common/Icons';

interface SessionsPageProps {
  data: SessionsHistoryData;
}

export const SessionsPage: React.FC<SessionsPageProps> = ({ data }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSessionId, setSelectedSessionId] = useState(data.sessions[0]?.id);

  const filteredSessions = data.sessions.filter(
    (s) =>
      s.date.toLowerCase().includes(searchTerm.toLowerCase()) ||
      s.status.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const currentSelected =
    data.sessions.find((s) => s.id === selectedSessionId) || data.sessions[0];

  return (
    <div className="sfm-page sfm-sessions-page" id="sessions-history-page">
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
          {/* Search box */}
          <div className="sfm-search-box">
            <SearchIcon size={14} color="#636673" />
            <input
              type="text"
              className="sfm-search-input"
              placeholder={data.searchPlaceholder}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              aria-label="Search study sessions"
            />
          </div>

          {/* Date dropdown button */}
          <button type="button" className="sfm-btn-dropdown" aria-label="Filter by date">
            <span>Date</span>
            <ChevronDownIcon size={12} color="#171A24" />
          </button>

          {/* Export icon */}
          <button
            type="button"
            className="sfm-icon-btn"
            aria-label="Export sessions history"
            title="Export sessions"
          >
            <ExportCloverIcon size={18} />
          </button>
        </div>
      </header>

      {/* Grid Content */}
      <div className="sfm-content-grid">
        {/* Card 1: Sessions Table */}
        <section
          className="sfm-card sfm-card-full sfm-sessions-table-card"
          aria-labelledby="sessions-table-heading"
        >
          <div className="sfm-table-responsive">
            <table className="sfm-table">
              <thead>
                <tr>
                  <th scope="col" className="sfm-th sfm-col-date">Date</th>
                  <th scope="col" className="sfm-th sfm-col-duration">Duration</th>
                  <th scope="col" className="sfm-th sfm-col-focus">Focus</th>
                  <th scope="col" className="sfm-th sfm-col-distractions">Distractions</th>
                  <th scope="col" className="sfm-th sfm-col-status">Status</th>
                </tr>
              </thead>
              <tbody>
                {filteredSessions.map((session: SessionRowData) => {
                  const isSelected = session.id === currentSelected.id;
                  return (
                    <tr
                      key={session.id}
                      className={`sfm-table-row ${isSelected ? 'is-selected' : ''}`}
                      onClick={() => setSelectedSessionId(session.id)}
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          setSelectedSessionId(session.id);
                        }
                      }}
                      role="button"
                      aria-label={`Select session for ${session.date}`}
                    >
                      <td className="sfm-td sfm-td-date">{session.date}</td>
                      <td className="sfm-td sfm-td-duration">{session.duration}</td>
                      <td className="sfm-td sfm-td-focus">{session.focus}</td>
                      <td className="sfm-td sfm-td-distractions">{session.distractions}</td>
                      <td className="sfm-td sfm-td-status">{session.status}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        {/* Card 2: Selected Session */}
        <section
          className="sfm-card sfm-card-full sfm-selected-session-card"
          aria-labelledby="selected-session-heading"
        >
          <div className="sfm-selected-header">
            <div className="sfm-selected-titles">
              <h2 id="selected-session-heading" className="sfm-card-heading">
                {`Selected Session · ${currentSelected.date}`}
              </h2>
              <p className="sfm-card-subheading">
                {`${currentSelected.duration} · ${currentSelected.focus} focus · ${currentSelected.distractions} distractions`}
              </p>
            </div>

            <div className="sfm-selected-causes">
              <span>{data.selectedSession.topCauses}</span>
            </div>
          </div>

          {/* Graphical timeline preview */}
          <div className="sfm-selected-timeline-container" aria-label="Session timeline preview">
            <div className="sfm-timeline-track-mini">
              <div
                className="sfm-segment sfm-segment-focused"
                style={{ flex: 35 }}
                title="Focused: 10:00 - 10:35"
              />
              <div className="sfm-segment-gap" style={{ flex: 1 }} />
              <div
                className="sfm-segment sfm-segment-distracted"
                style={{ flex: 8 }}
                title="Distracted: 10:38 - 10:46"
              />
              <div className="sfm-segment-gap" style={{ flex: 1 }} />
              <div
                className="sfm-segment sfm-segment-focused"
                style={{ flex: 42 }}
                title="Focused: 10:48 - 11:30"
              />
              <div className="sfm-segment-gap" style={{ flex: 1 }} />
              <div
                className="sfm-segment sfm-segment-distracted"
                style={{ flex: 12 }}
                title="Distracted: 11:32 - 11:44"
              />
              <div className="sfm-segment-gap" style={{ flex: 1 }} />
              <div
                className="sfm-segment sfm-segment-focused"
                style={{ flex: 45 }}
                title="Focused: 11:46 - 12:31"
              />
              <div className="sfm-segment-gap" style={{ flex: 1 }} />
              <div
                className="sfm-segment sfm-segment-distracted"
                style={{ flex: 6 }}
                title="Distracted: 12:33 - 12:39"
              />
              <div className="sfm-segment-gap" style={{ flex: 1 }} />
              <div
                className="sfm-segment sfm-segment-focused"
                style={{ flex: 43 }}
                title="Focused: 12:41 - 1:24"
              />
            </div>

            <div className="sfm-selected-timestamps">
              <span className="sfm-time-tick">{data.selectedSession.startTime}</span>
              <span className="sfm-time-tick">{data.selectedSession.endTime}</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};
