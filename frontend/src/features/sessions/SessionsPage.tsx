import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { StudySession, StudySessionDetail, FeedbackType } from '../../types/session';
import { fetchSessionHistory, fetchSessionDetail, submitSessionFeedback } from '../../services/sessionApi';
import {
  SearchIcon,
  ChevronDownIcon,
  ExportCloverIcon,
} from '../../components/common/Icons';

const CATEGORY_DISPLAY_NAMES: Record<string, string> = {
  looking_away: 'Looking Away',
  phone_use: 'Phone Use',
  yawning: 'Yawning',
  drowsy: 'Drowsiness',
  leaning_back: 'Bad Posture',
  away_from_desk: 'Away From Seat',
};

function formatCategory(cat: string | null | undefined): string {
  if (!cat) return 'Distraction';
  return CATEGORY_DISPLAY_NAMES[cat] || cat.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
}

export interface SessionsPageProps {
  initialSessions?: StudySession[];
  initialDetail?: StudySessionDetail | null;
}

function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const secs = s % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return secs > 0 ? `${m}m ${secs}s` : `${m}m`;
  return `${secs}s`;
}

function formatDate(isoString: string): string {
  try {
    const d = new Date(isoString);
    return d.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return isoString;
  }
}

function formatTime(isoString: string | null): string {
  if (!isoString) return 'In progress';
  try {
    const d = new Date(isoString);
    return d.toLocaleTimeString(undefined, {
      hour: 'numeric',
      minute: '2-digit',
    });
  } catch {
    return isoString;
  }
}

export const SessionsPage: React.FC<SessionsPageProps> = ({
  initialSessions,
  initialDetail,
}) => {
  const [sessions, setSessions] = useState<StudySession[]>(initialSessions || []);
  const [total, setTotal] = useState<number>(initialSessions ? initialSessions.length : 0);
  const [page, setPage] = useState<number>(1);
  const [pageSize] = useState<number>(10);
  const [totalPages, setTotalPages] = useState<number>(
    initialSessions ? Math.max(1, Math.ceil(initialSessions.length / 10)) : 1
  );
  const [isLoading, setIsLoading] = useState<boolean>(initialSessions === undefined);
  const [error, setError] = useState<string | null>(null);

  const [searchTerm, setSearchTerm] = useState<string>('');
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(
    initialDetail?.id || initialSessions?.[0]?.id || null
  );
  const [selectedDetail, setSelectedDetail] = useState<StudySessionDetail | null>(
    initialDetail || null
  );
  const [isLoadingDetail, setIsLoadingDetail] = useState<boolean>(false);

  // Feedback states
  const [submittingEventId, setSubmittingEventId] = useState<string | null>(null);
  const [feedbackSuccess, setFeedbackSuccess] = useState<string | null>(null);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);

  const [showMissedForm, setShowMissedForm] = useState<boolean>(false);
  const [missedCategory, setMissedCategory] = useState<string>('phone_use');
  const [missedNote, setMissedNote] = useState<string>('');
  const [isSubmittingMissed, setIsSubmittingMissed] = useState<boolean>(false);

  const [showOtherForm, setShowOtherForm] = useState<boolean>(false);
  const [otherNote, setOtherNote] = useState<string>('');
  const [isSubmittingOther, setIsSubmittingOther] = useState<boolean>(false);

  const handleEventFeedback = async (eventId: string, type: FeedbackType) => {
    if (!selectedSessionId || submittingEventId) return;
    setSubmittingEventId(eventId);
    setFeedbackError(null);
    setFeedbackSuccess(null);
    try {
      const fb = await submitSessionFeedback(selectedSessionId, {
        detectionEventId: eventId,
        feedbackType: type,
      });
      setFeedbackSuccess('Feedback recorded.');
      setSelectedDetail((prev) => {
        if (!prev) return prev;
        const updatedEvents = prev.events.map((e) =>
          e.id === eventId ? { ...e, feedback: fb } : e
        );
        const existingIdx = (prev.feedbacks || []).findIndex(
          (f) => f.detectionEventId === eventId
        );
        const updatedFeedbacks = [...(prev.feedbacks || [])];
        if (existingIdx >= 0) {
          updatedFeedbacks[existingIdx] = fb;
        } else {
          updatedFeedbacks.push(fb);
        }
        return {
          ...prev,
          events: updatedEvents,
          feedbacks: updatedFeedbacks,
        };
      });
    } catch (err: any) {
      setFeedbackError(err.message || 'Failed to submit feedback.');
    } finally {
      setSubmittingEventId(null);
    }
  };

  const handleSubmitMissedDetection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSessionId || isSubmittingMissed) return;
    setIsSubmittingMissed(true);
    setFeedbackError(null);
    setFeedbackSuccess(null);
    try {
      const fb = await submitSessionFeedback(selectedSessionId, {
        feedbackType: 'missed_detection',
        category: missedCategory,
        note: missedNote.trim() || undefined,
      });
      setFeedbackSuccess(`Missed distraction recorded: ${formatCategory(missedCategory)}.`);
      setMissedNote('');
      setShowMissedForm(false);
      setSelectedDetail((prev) => {
        if (!prev) return prev;
        const existingIdx = (prev.feedbacks || []).findIndex(
          (f) => f.feedbackType === 'missed_detection' && f.category === fb.category
        );
        const updatedFeedbacks = [...(prev.feedbacks || [])];
        if (existingIdx >= 0) {
          updatedFeedbacks[existingIdx] = fb;
        } else {
          updatedFeedbacks.push(fb);
        }
        return {
          ...prev,
          feedbacks: updatedFeedbacks,
        };
      });
    } catch (err: any) {
      setFeedbackError(err.message || 'Failed to submit missed distraction report.');
    } finally {
      setIsSubmittingMissed(false);
    }
  };

  const handleSubmitOther = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSessionId || isSubmittingOther || !otherNote.trim()) return;
    setIsSubmittingOther(true);
    setFeedbackError(null);
    setFeedbackSuccess(null);
    try {
      const fb = await submitSessionFeedback(selectedSessionId, {
        feedbackType: 'other',
        note: otherNote.trim(),
      });
      setFeedbackSuccess('Session feedback note recorded.');
      setOtherNote('');
      setShowOtherForm(false);
      setSelectedDetail((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          feedbacks: [...(prev.feedbacks || []), fb],
        };
      });
    } catch (err: any) {
      setFeedbackError(err.message || 'Failed to submit feedback note.');
    } finally {
      setIsSubmittingOther(false);
    }
  };

  // Load paginated sessions
  const loadSessions = useCallback(async (pageNum: number) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetchSessionHistory(pageNum, pageSize);
      setSessions(res.items);
      setTotal(res.total);
      setPage(res.page);
      setTotalPages(res.totalPages);

      if (res.items.length > 0) {
        setSelectedSessionId((prev) => {
          const exists = res.items.some((s) => s.id === prev);
          return exists ? prev : res.items[0].id;
        });
      } else {
        setSelectedSessionId(null);
        setSelectedDetail(null);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load study sessions');
    } finally {
      setIsLoading(false);
    }
  }, [pageSize]);

  useEffect(() => {
    if (initialSessions !== undefined) return;
    loadSessions(page);
  }, [loadSessions, page, initialSessions]);


  // Load detail when selectedSessionId changes
  useEffect(() => {
    if (!selectedSessionId) {
      setSelectedDetail(null);
      return;
    }
    let isCancelled = false;
    setIsLoadingDetail(true);
    fetchSessionDetail(selectedSessionId)
      .then((detail) => {
        if (!isCancelled) setSelectedDetail(detail);
      })
      .catch(() => {
        // Fallback to basic session if detail lookup fails
        if (!isCancelled) {
          const basic = sessions.find((s) => s.id === selectedSessionId);
          if (basic) {
            setSelectedDetail({
              ...basic,
              events: [],
              feedbacks: [],
              topCauses: 'No distractions recorded',
              categoryBreakdown: [],
            });
          }
        }
      })
      .finally(() => {
        if (!isCancelled) setIsLoadingDetail(false);
      });

    return () => {
      isCancelled = true;
    };
  }, [selectedSessionId, sessions]);

  // Client search filter on the current page items
  const filteredSessions = useMemo(() => {
    if (!searchTerm.trim()) return sessions;
    const term = searchTerm.toLowerCase();
    return sessions.filter((s) => {
      const dStr = formatDate(s.startedAt).toLowerCase();
      const statusStr = s.status.toLowerCase();
      return dStr.includes(term) || statusStr.includes(term);
    });
  }, [sessions, searchTerm]);

  const currentSelectedSession = useMemo(() => {
    return sessions.find((s) => s.id === selectedSessionId) || sessions[0] || null;
  }, [sessions, selectedSessionId]);

  return (
    <div className="sfm-page sfm-sessions-page" id="sessions-history-page">
      {/* Header */}
      <header className="sfm-page-header">
        <div className="sfm-header-left">
          <div className="sfm-avatar-circle" aria-label="User Avatar">
            <span>S</span>
          </div>
          <div className="sfm-header-titles">
            <h1 className="sfm-page-title">Sessions History</h1>
            <p className="sfm-page-subtitle">
              Review every study session and see what broke your focus.
            </p>
          </div>
        </div>

        <div className="sfm-header-right">
          {/* Search box */}
          <div className="sfm-search-box">
            <SearchIcon size={14} color="#636673" />
            <input
              type="text"
              className="sfm-search-input"
              placeholder="Search sessions"
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

      {/* Main Grid Content */}
      <div className="sfm-content-grid">
        {/* Card 1: Sessions Table */}
        <section
          className="sfm-card sfm-card-full sfm-sessions-table-card"
          aria-labelledby="sessions-table-heading"
        >
          {isLoading ? (
            <div className="sfm-empty-state-box" id="sessions-loading-state">
              <p className="sfm-empty-state-title">Loading sessions...</p>
              <p className="sfm-empty-state-desc">Retrieving your study history.</p>
            </div>
          ) : error ? (
            <div className="sfm-empty-state-box" id="sessions-error-state">
              <p className="sfm-empty-state-title">Error loading sessions</p>
              <p className="sfm-empty-state-desc">{error}</p>
            </div>
          ) : sessions.length === 0 ? (
            <div className="sfm-empty-state-box" id="sessions-empty-state">
              <p className="sfm-empty-state-title">No study sessions yet.</p>
              <p className="sfm-empty-state-desc">
                Start a study session to track your focus and distraction patterns over time.
              </p>
            </div>
          ) : (
            <>
              <div className="sfm-table-responsive">
                <table className="sfm-table" aria-label="Study sessions history table">
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
                    {filteredSessions.map((session) => {
                      const isSelected = session.id === currentSelectedSession?.id;
                      const focusText =
                        session.focusScore !== null ? `${Math.round(session.focusScore)}%` : '—';
                      const statusText =
                        session.status.charAt(0).toUpperCase() + session.status.slice(1);

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
                          aria-label={`Select session from ${formatDate(session.startedAt)}`}
                        >
                          <td className="sfm-td sfm-td-date">{formatDate(session.startedAt)}</td>
                          <td className="sfm-td sfm-td-duration">
                            {formatDuration(session.totalDurationSeconds)}
                          </td>
                          <td className="sfm-td sfm-td-focus">{focusText}</td>
                          <td className="sfm-td sfm-td-distractions">{session.distractionCount}</td>
                          <td className="sfm-td sfm-td-status">{statusText}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Pagination Controls */}
              {total > 0 && (
                <div className="sfm-pagination-bar" id="sessions-pagination-controls">
                  <span className="sfm-pagination-info">
                    Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total} sessions
                  </span>
                  <div className="sfm-pagination-actions">
                    <button
                      type="button"
                      className="sfm-btn-page"
                      id="btn-prev-page"
                      disabled={page <= 1}
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                    >
                      Previous
                    </button>
                    <span className="sfm-page-number">
                      Page {page} of {totalPages}
                    </span>
                    <button
                      type="button"
                      className="sfm-btn-page"
                      id="btn-next-page"
                      disabled={page >= totalPages}
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </section>

        {/* Card 2: Selected Session Detail */}
        {currentSelectedSession && (
          <section
            className="sfm-card sfm-card-full sfm-selected-session-card"
            id="selected-session-card"
            aria-labelledby="selected-session-heading"
          >
            <div className="sfm-selected-header">
              <div className="sfm-selected-titles">
                <h2 id="selected-session-heading" className="sfm-card-heading">
                  Selected Session · {formatDate(currentSelectedSession.startedAt)}
                </h2>
                <p className="sfm-card-subheading">
                  {formatDuration(currentSelectedSession.totalDurationSeconds)} ·{' '}
                  {currentSelectedSession.focusScore !== null
                    ? `${Math.round(currentSelectedSession.focusScore)}% focus`
                    : 'Focus in progress'}{' '}
                  · {currentSelectedSession.distractionCount} distractions
                </p>
              </div>

              <div className="sfm-selected-causes">
                <span>{selectedDetail?.topCauses || 'Analyzing session...'}</span>
              </div>
            </div>

            {/* Graphical timeline preview */}
            <div className="sfm-selected-timeline-container" aria-label="Session timeline preview">
              <div className="sfm-timeline-track-mini">
                {currentSelectedSession.totalDurationSeconds > 0 ? (
                  <>
                    <div
                      className="sfm-segment sfm-segment-focused"
                      style={{
                        flex: Math.max(1, Math.round(currentSelectedSession.focusedSeconds || 1)),
                      }}
                      title={`Focused: ${formatDuration(currentSelectedSession.focusedSeconds)}`}
                    />
                    {currentSelectedSession.distractedSeconds > 0 && (
                      <>
                        <div className="sfm-segment-gap" style={{ flex: 1 }} />
                        <div
                          className="sfm-segment sfm-segment-distracted"
                          style={{
                            flex: Math.max(1, Math.round(currentSelectedSession.distractedSeconds)),
                          }}
                          title={`Distracted: ${formatDuration(currentSelectedSession.distractedSeconds)}`}
                        />
                      </>
                    )}
                    {currentSelectedSession.awaySeconds > 0 && (
                      <>
                        <div className="sfm-segment-gap" style={{ flex: 1 }} />
                        <div
                          className="sfm-segment sfm-segment-away"
                          style={{
                            flex: Math.max(1, Math.round(currentSelectedSession.awaySeconds)),
                            backgroundColor: '#9CA3AF',
                          }}
                          title={`Away: ${formatDuration(currentSelectedSession.awaySeconds)}`}
                        />
                      </>
                    )}
                  </>
                ) : (
                  <div
                    className="sfm-segment sfm-segment-focused"
                    style={{ flex: 1 }}
                    title="Active Session"
                  />
                )}
              </div>

              <div className="sfm-selected-timestamps">
                <span className="sfm-time-tick">
                  {formatTime(currentSelectedSession.startedAt)}
                </span>
                <span className="sfm-time-tick">
                  {formatTime(currentSelectedSession.endedAt)}
                </span>
              </div>
            </div>

            {/* Discrete Detection Events List */}
            <div className="sfm-detail-events-section" id="session-events-list">
              <h3 className="sfm-detail-events-title">Detected Distraction Events</h3>
              {isLoadingDetail ? (
                <p className="sfm-empty-state-desc">Loading events...</p>
              ) : !selectedDetail || selectedDetail.events.length === 0 ? (
                <p className="sfm-empty-state-desc">
                  No distraction events recorded during this session.
                </p>
              ) : (
                <div className="sfm-events-list">
                  {selectedDetail.events.map((evt) => (
                    <div key={evt.id} className="sfm-event-item" id={`event-item-${evt.id}`}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <span className="sfm-event-cat-badge">
                          <span className="sfm-event-dot" />
                          {formatCategory(evt.eventType)}
                        </span>
                        <span className="sfm-event-times">
                          {formatTime(evt.startedAt)}
                          {evt.endedAt ? ` — ${formatTime(evt.endedAt)}` : ' (ongoing)'}
                        </span>
                        <span className="sfm-event-duration">
                          {evt.durationSeconds !== null
                            ? formatDuration(evt.durationSeconds)
                            : '—'}
                        </span>
                      </div>

                      {/* Event Feedback Controls */}
                      <div className="sfm-event-feedback-controls">
                        {evt.feedback ? (
                          <>
                            {evt.feedback.feedbackType === 'correct_detection' && (
                              <span
                                className="sfm-feedback-badge sfm-badge-correct"
                                id={`feedback-status-${evt.id}`}
                              >
                                ✓ Correct
                              </span>
                            )}
                            {evt.feedback.feedbackType === 'false_positive' && (
                              <span
                                className="sfm-feedback-badge sfm-badge-false-positive"
                                id={`feedback-status-${evt.id}`}
                              >
                                ✗ False Positive
                              </span>
                            )}
                            {evt.feedback.feedbackType === 'other' && (
                              <span
                                className="sfm-feedback-badge sfm-badge-other"
                                id={`feedback-status-${evt.id}`}
                              >
                                💬 Note
                              </span>
                            )}
                            <button
                              type="button"
                              className="sfm-feedback-btn-subtle"
                              id={`btn-edit-feedback-${evt.id}`}
                              disabled={submittingEventId === evt.id}
                              onClick={() => {
                                const newType =
                                  evt.feedback?.feedbackType === 'correct_detection'
                                    ? 'false_positive'
                                    : 'correct_detection';
                                handleEventFeedback(evt.id, newType);
                              }}
                              title="Switch feedback classification"
                            >
                              Change
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              type="button"
                              className="sfm-feedback-btn sfm-btn-correct"
                              id={`btn-feedback-correct-${evt.id}`}
                              disabled={submittingEventId === evt.id}
                              onClick={() => handleEventFeedback(evt.id, 'correct_detection')}
                            >
                              {submittingEventId === evt.id ? 'Saving...' : 'Correct'}
                            </button>
                            <button
                              type="button"
                              className="sfm-feedback-btn sfm-btn-false-positive"
                              id={`btn-feedback-fp-${evt.id}`}
                              disabled={submittingEventId === evt.id}
                              onClick={() => handleEventFeedback(evt.id, 'false_positive')}
                            >
                              {submittingEventId === evt.id ? 'Saving...' : 'False positive'}
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Session Feedback & Missed Detections Section */}
            <div className="sfm-session-feedback-section" id="session-feedback-section">
              <div className="sfm-feedback-header-row">
                <h4 className="sfm-feedback-section-title">Session Accuracy & Feedback</h4>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    type="button"
                    className="sfm-btn-toggle-feedback"
                    id="btn-toggle-missed-detection"
                    onClick={() => {
                      setShowMissedForm(!showMissedForm);
                      setShowOtherForm(false);
                    }}
                  >
                    {showMissedForm ? 'Cancel' : 'Did we miss a distraction?'}
                  </button>
                  <button
                    type="button"
                    className="sfm-btn-toggle-feedback"
                    id="btn-toggle-other-feedback"
                    onClick={() => {
                      setShowOtherForm(!showOtherForm);
                      setShowMissedForm(false);
                    }}
                  >
                    {showOtherForm ? 'Cancel' : 'General note'}
                  </button>
                </div>
              </div>

              {/* Status notifications */}
              {feedbackSuccess && (
                <div className="sfm-feedback-alert sfm-feedback-alert-success" id="feedback-success-msg">
                  {feedbackSuccess}
                </div>
              )}
              {feedbackError && (
                <div className="sfm-feedback-alert sfm-feedback-alert-error" id="feedback-error-msg">
                  {feedbackError}
                </div>
              )}

              {/* Missed Detection Form */}
              {showMissedForm && (
                <form
                  className="sfm-feedback-card sfm-feedback-form"
                  id="form-missed-detection"
                  onSubmit={handleSubmitMissedDetection}
                >
                  <label style={{ fontSize: '12px', fontWeight: 600 }}>Report Missed Distraction</label>
                  <div className="sfm-feedback-row">
                    <select
                      className="sfm-feedback-select"
                      id="select-missed-category"
                      value={missedCategory}
                      onChange={(e) => setMissedCategory(e.target.value)}
                    >
                      <option value="phone_use">Phone Use</option>
                      <option value="looking_away">Looking Away</option>
                      <option value="yawning">Yawning</option>
                      <option value="drowsy">Drowsiness</option>
                      <option value="leaning_back">Bad Posture</option>
                      <option value="away_from_desk">Away From Seat</option>
                    </select>
                    <input
                      type="text"
                      className="sfm-feedback-input"
                      id="input-missed-note"
                      placeholder="Optional note (e.g. Looked at phone at 15m)"
                      maxLength={1000}
                      value={missedNote}
                      onChange={(e) => setMissedNote(e.target.value)}
                    />
                    <button
                      type="submit"
                      className="sfm-feedback-submit-btn"
                      id="btn-submit-missed"
                      disabled={isSubmittingMissed}
                    >
                      {isSubmittingMissed ? 'Submitting...' : 'Record Missed'}
                    </button>
                  </div>
                </form>
              )}

              {/* Other Feedback Form */}
              {showOtherForm && (
                <form
                  className="sfm-feedback-card sfm-feedback-form"
                  id="form-other-feedback"
                  onSubmit={handleSubmitOther}
                >
                  <label style={{ fontSize: '12px', fontWeight: 600 }}>Session Feedback Note</label>
                  <div className="sfm-feedback-row">
                    <input
                      type="text"
                      className="sfm-feedback-input"
                      id="input-other-note"
                      placeholder="Optional note on lighting, seating, or detector accuracy..."
                      maxLength={1000}
                      value={otherNote}
                      onChange={(e) => setOtherNote(e.target.value)}
                      required
                    />
                    <button
                      type="submit"
                      className="sfm-feedback-submit-btn"
                      id="btn-submit-other"
                      disabled={isSubmittingOther || !otherNote.trim()}
                    >
                      {isSubmittingOther ? 'Submitting...' : 'Submit Note'}
                    </button>
                  </div>
                </form>
              )}

              {/* List of previously submitted missed detections & other session notes */}
              {selectedDetail &&
                selectedDetail.feedbacks &&
                selectedDetail.feedbacks.some((f) => !f.detectionEventId) && (
                  <div className="sfm-missed-list" id="session-feedback-list">
                    {selectedDetail.feedbacks
                      .filter((f) => !f.detectionEventId)
                      .map((f) => (
                        <div key={f.id} className="sfm-missed-item" id={`feedback-item-${f.id}`}>
                          <div>
                            {f.feedbackType === 'missed_detection' ? (
                              <span className="sfm-missed-badge">
                                Missed: {formatCategory(f.category)}
                              </span>
                            ) : (
                              <span className="sfm-feedback-badge sfm-badge-other">Session Note</span>
                            )}
                            {f.note && <span className="sfm-missed-note">"{f.note}"</span>}
                          </div>
                          <span className="sfm-missed-time">{formatTime(f.createdAt)}</span>
                        </div>
                      ))}
                  </div>
                )}
            </div>
          </section>
        )}
      </div>
    </div>
  );
};
