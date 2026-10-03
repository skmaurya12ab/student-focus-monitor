import React, { useEffect, useState, useCallback } from 'react';
import { AppShell } from '../components/layout/AppShell';
import { checkBackendHealth } from '../services/api';
import { BackendStatus } from '../types/api';
import { AuthProvider } from '../context/AuthContext';
import { SessionProvider } from '../context/SessionContext';
import { LiveTransportProvider } from '../context/LiveTransportContext';

export const App: React.FC = () => {
  const [backendStatus, setBackendStatus] = useState<BackendStatus>('checking');

  const verifyHealth = useCallback(async () => {
    try {
      setBackendStatus('checking');
      const isHealthy = await checkBackendHealth();
      setBackendStatus(isHealthy ? 'connected' : 'unavailable');
    } catch {
      setBackendStatus('unavailable');
    }
  }, []);

  useEffect(() => {
    verifyHealth();
  }, [verifyHealth]);

  return (
    <AuthProvider>
      <SessionProvider>
        <LiveTransportProvider>
          <div className="sfm-app-root" data-backend-status={backendStatus}>
            <AppShell />
          </div>
        </LiveTransportProvider>
      </SessionProvider>
    </AuthProvider>
  );
};

export default App;
