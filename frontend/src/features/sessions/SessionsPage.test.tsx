import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderToString } from 'react-dom/server';
import { SessionsPage } from './SessionsPage';
import { StudySession, StudySessionDetail } from '../../types/session';

describe('SessionsPage component tests (Phase 10 Session History)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockSessions: StudySession[] = [
    {
      id: 'session-uuid-1',
      userId: 'u-1',
      status: 'completed',
      startedAt: '2026-10-04T10:00:00Z',
      endedAt: '2026-10-04T11:00:00Z',
      totalDurationSeconds: 3600,
      focusedSeconds: 3000,
      distractedSeconds: 400,
      awaySeconds: 200,
      focusScore: 83.33,
      distractionCount: 2,
      detectorVersion: 'v4',
      featureSchemaVersion: 'telemetry_v1',
      createdAt: '2026-10-04T10:00:00Z',
      updatedAt: '2026-10-04T11:00:00Z',
    },
    {
      id: 'session-uuid-2',
      userId: 'u-1',
      status: 'completed',
      startedAt: '2026-10-03T14:00:00Z',
      endedAt: '2026-10-03T14:45:00Z',
      totalDurationSeconds: 2700,
      focusedSeconds: 2500,
      distractedSeconds: 200,
      awaySeconds: 0,
      focusScore: 92.59,
      distractionCount: 1,
      detectorVersion: 'v4',
      featureSchemaVersion: 'telemetry_v1',
      createdAt: '2026-10-03T14:00:00Z',
      updatedAt: '2026-10-03T14:45:00Z',
    },
  ];

  const mockDetail: StudySessionDetail = {
    ...mockSessions[0],
    topCauses: 'Top causes: Phone Use · Looking Away',
    categoryBreakdown: [
      { category: 'phone_use', label: 'Phone Use', count: 1, durationSeconds: 200 },
      { category: 'looking_away', label: 'Looking Away', count: 1, durationSeconds: 200 },
    ],
    events: [
      {
        id: 'evt-1',
        sessionId: 'session-uuid-1',
        eventType: 'phone_use',
        startedAt: '2026-10-04T10:15:00Z',
        endedAt: '2026-10-04T10:18:20Z',
        durationSeconds: 200,
        detectorVersion: 'v4',
        metadataJson: null,
        createdAt: '2026-10-04T10:15:00Z',
      },
    ],
    feedbacks: [],
  };

  it('renders loading state when initialSessions is not provided', () => {
    const html = renderToString(<SessionsPage />);
    expect(html).toContain('Loading sessions...');
    expect(html).toContain('Retrieving your study history.');
  });

  it('renders empty state when user has no study sessions, without mock numbers', () => {
    const html = renderToString(<SessionsPage initialSessions={[]} />);
    expect(html).toContain('No study sessions yet.');
    expect(html).toContain(
      'Start a study session to track your focus and distraction patterns over time.'
    );

    // Verify Phase 3 mock values do not leak
    expect(html).not.toContain('01:42:18');
    expect(html).not.toContain('00:18:34');
    expect(html).not.toContain('00:04:12');
    expect(html).not.toContain('3h 24m');
  });

  it('renders real sessions table, pagination, and selected session detail with discrete events', () => {
    const rawHtml = renderToString(
      <SessionsPage initialSessions={mockSessions} initialDetail={mockDetail} />
    );
    const html = rawHtml.replace(/<!--.*?-->/g, '');

    // Table headers and columns
    expect(html).toContain('Sessions History');
    expect(html).toContain('Date');
    expect(html).toContain('Duration');
    expect(html).toContain('Focus');
    expect(html).toContain('Distractions');
    expect(html).toContain('Status');

    // Row values
    expect(html).toContain('83%');
    expect(html).toContain('93%');
    expect(html).toContain('Completed');

    // Pagination info
    expect(html).toContain('Showing 1–2 of 2 sessions');
    expect(html).toContain('Page 1 of 1');
    expect(html).toContain('Previous');
    expect(html).toContain('Next');

    // Selected session card
    expect(html).toContain('Selected Session');
    expect(html).toContain('Top causes: Phone Use · Looking Away');

    // Detected events list
    expect(html).toContain('Detected Distraction Events');
    expect(html).toContain('Phone Use');
    expect(html).toContain('3m 20s');

    // Phase 11 Event Feedback buttons rendered
    expect(html).toContain('Correct');
    expect(html).toContain('False positive');

    // Phase 11 Missed Detection and Session Feedback toggle buttons rendered
    expect(html).toContain('Session Accuracy &amp; Feedback');
    expect(html).toContain('Did we miss a distraction?');
    expect(html).toContain('General note');
  });

  it('renders feedback badges and Change button when events have existing feedback', () => {
    const detailWithFeedback: StudySessionDetail = {
      ...mockDetail,
      events: [
        {
          ...mockDetail.events[0],
          feedback: {
            id: 'fb-1',
            sessionId: 'session-uuid-1',
            detectionEventId: 'evt-1',
            feedbackType: 'correct_detection',
            category: null,
            note: 'Verified phone checking',
            createdAt: '2026-10-04T10:20:00Z',
          },
        },
      ],
      feedbacks: [
        {
          id: 'fb-2',
          sessionId: 'session-uuid-1',
          detectionEventId: null,
          feedbackType: 'missed_detection',
          category: 'phone_use',
          note: 'Was reading text message',
          createdAt: '2026-10-04T10:25:00Z',
        },
      ],
    };

    const rawHtml = renderToString(
      <SessionsPage initialSessions={mockSessions} initialDetail={detailWithFeedback} />
    );
    const html = rawHtml.replace(/<!--.*?-->/g, '');

    // Event feedback badge
    expect(html).toContain('✓ Correct');
    expect(html).toContain('Change');

    // Session-level feedback item
    expect(html).toContain('Missed: Phone Use');
    expect(html).toContain('Was reading text message');
  });
});
