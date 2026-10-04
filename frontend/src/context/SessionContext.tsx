/**
 * SessionContext: Manages authoritative Study Session Lifecycle state.
 * Survives page refreshes, navigation, and component remounts.
 */
import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from 'react';
import { StudySession } from '../types/session';
import {
  fetchActiveStudySession,
  fetchLatestStudySession,
  startStudySession,
  stopStudySession,
} from '../services/sessionApi';
import { useAuth } from './AuthContext';

interface SessionContextType {
  activeSession: StudySession | null;
  lastCompletedSession: StudySession | null;
  isLoading: boolean;
  isStarting: boolean;
  isStopping: boolean;
  sessionError: string | null;
  elapsedSeconds: number;
  isBackendUnavailable: boolean;
  startSession: (notes?: string) => Promise<StudySession>;
  stopSession: () => Promise<StudySession | null>;
  refreshActiveSession: () => Promise<void>;
  clearSessionError: () => void;
}

const SessionContext = createContext<SessionContextType | undefined>(undefined);

export const SessionProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { isAuthenticated, user } = useAuth();
  const [activeSession, setActiveSession] = useState<StudySession | null>(null);
  const [lastCompletedSession, setLastCompletedSession] = useState<StudySession | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isStarting, setIsStarting] = useState<boolean>(false);
  const [isStopping, setIsStopping] = useState<boolean>(false);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [isBackendUnavailable, setIsBackendUnavailable] = useState<boolean>(false);
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);

  const clearSessionError = useCallback(() => {
    setSessionError(null);
  }, []);

  const refreshActiveSession = useCallback(async () => {
    if (!isAuthenticated) {
      setActiveSession(null);
      setLastCompletedSession(null);
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);
      setSessionError(null);
      const session = await fetchActiveStudySession();
      setActiveSession(session);
      if (!session) {
        // Retrieve student's most recent completed session
        const latest = await fetchLatestStudySession();
        setLastCompletedSession(latest);
      }
      setIsBackendUnavailable(false);
    } catch (err: any) {
      if (err.message === 'BACKEND_UNAVAILABLE') {
        setIsBackendUnavailable(true);
      } else {
        setSessionError(err.message || 'Failed to fetch active session');
      }
      setActiveSession(null);
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  // Initial load and whenever auth status changes
  useEffect(() => {
    refreshActiveSession();
  }, [refreshActiveSession, user]);

  // Authoritative elapsed timer counting seconds from startedAt
  useEffect(() => {
    if (!activeSession || activeSession.status !== 'active') {
      setElapsedSeconds(0);
      return;
    }

    const calculateElapsed = () => {
      const startTime = new Date(activeSession.startedAt).getTime();
      const diff = Math.max(0, Math.floor((Date.now() - startTime) / 1000));
      setElapsedSeconds(diff);
    };

    calculateElapsed();
    const interval = setInterval(calculateElapsed, 1000);
    return () => clearInterval(interval);
  }, [activeSession]);

  const startSession = async (notes?: string): Promise<StudySession> => {
    if (isStarting) {
      throw new Error('Session start already in progress');
    }

    try {
      setIsStarting(true);
      setSessionError(null);
      const session = await startStudySession({ notes });
      setActiveSession(session);
      setIsBackendUnavailable(false);
      return session;
    } catch (err: any) {
      if (err.message === 'BACKEND_UNAVAILABLE') {
        setIsBackendUnavailable(true);
      } else {
        setSessionError(err.message || 'Failed to start session');
      }
      throw err;
    } finally {
      setIsStarting(false);
    }
  };

  const stopSession = async (): Promise<StudySession | null> => {
    if (!activeSession) {
      return null;
    }
    if (isStopping) {
      throw new Error('Session stop already in progress');
    }

    try {
      setIsStopping(true);
      setSessionError(null);
      const completedSession = await stopStudySession(activeSession.id);
      setActiveSession(null);
      setLastCompletedSession(completedSession);
      setIsBackendUnavailable(false);
      return completedSession;
    } catch (err: any) {
      if (err.message === 'BACKEND_UNAVAILABLE') {
        setIsBackendUnavailable(true);
      } else {
        setSessionError(err.message || 'Failed to stop session');
      }
      throw err;
    } finally {
      setIsStopping(false);
    }
  };

  return (
    <SessionContext.Provider
      value={{
        activeSession,
        lastCompletedSession,
        isLoading,
        isStarting,
        isStopping,
        sessionError,
        elapsedSeconds,
        isBackendUnavailable,
        startSession,
        stopSession,
        refreshActiveSession,
        clearSessionError,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
};

export const useSession = (): SessionContextType => {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
};
