import React, { useEffect, useState, useCallback } from 'react';
import { checkBackendHealth, API_BASE_URL } from '../services/api';
import { BackendStatus } from '../types/api';

export const App: React.FC = () => {
  const [backendStatus, setBackendStatus] = useState<BackendStatus>('checking');

  const verifyHealth = useCallback(async () => {
    setBackendStatus('checking');
    const isHealthy = await checkBackendHealth();
    setBackendStatus(isHealthy ? 'connected' : 'unavailable');
  }, []);

  useEffect(() => {
    verifyHealth();
  }, [verifyHealth]);

  return (
    <div className="bootstrap-container">
      <div className="header-section">
        <span className="badge">Phase 1 — Bootstrap</span>
        <h1>Student Focus Monitor</h1>
        <p className="description">
          Development environment verification screen. Core services and health
          monitoring foundations are established.
        </p>
      </div>

      <div className="status-grid">
        {/* Frontend Status */}
        <div className="status-card" id="frontend-status-card">
          <div className="status-label-group">
            <span className="status-title">Frontend</span>
            <span className="status-subtitle">Vite + React + TypeScript</span>
          </div>
          <div className="status-pill running" id="frontend-status-pill">
            <span className="status-dot"></span>
            <span>Frontend is running.</span>
          </div>
        </div>

        {/* Backend Status */}
        <div className="status-card" id="backend-status-card">
          <div className="status-label-group">
            <span className="status-title">Backend status:</span>
            <span className="status-subtitle">
              Target: <code>{API_BASE_URL}/api/health</code>
            </span>
          </div>
          <div
            className={`status-pill ${backendStatus}`}
            id="backend-status-pill"
          >
            <span className="status-dot"></span>
            <span>
              {backendStatus === 'checking' && 'Checking...'}
              {backendStatus === 'connected' && 'Backend: Connected'}
              {backendStatus === 'unavailable' && 'Backend: Unavailable'}
            </span>
          </div>
        </div>
      </div>

      <div className="action-section">
        <button
          type="button"
          className="button-retry"
          onClick={verifyHealth}
          disabled={backendStatus === 'checking'}
          id="btn-recheck"
        >
          {backendStatus === 'checking' ? 'Checking...' : 'Re-check Backend'}
        </button>
      </div>

      <div className="meta-footer">
        <span>Environment: <code>development</code></span>
        <span>Target Port: <code>5173</code></span>
      </div>
    </div>
  );
};

export default App;
