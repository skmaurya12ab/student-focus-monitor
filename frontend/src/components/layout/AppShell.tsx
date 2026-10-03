import React, { useState, useEffect, useCallback } from 'react';
import { NavigationTab } from '../../types/dashboard';
import { Sidebar } from './Sidebar';
import { HomePage } from '../../features/home/HomePage';
import { AnalyticsPage } from '../../features/analytics/AnalyticsPage';
import { SessionsPage } from '../../features/sessions/SessionsPage';
import { SettingsPage } from '../../features/settings/SettingsPage';
import {
  mockHomeData,
  mockAnalyticsData,
  mockSessionsData,
  mockSettingsData,
} from '../../data/mock';

const pathToTab = (path: string): NavigationTab => {
  const normalized = path.replace(/^\/|\/$/g, '').toLowerCase();
  if (normalized === 'analytics') return 'analytics';
  if (normalized === 'sessions') return 'sessions';
  if (normalized === 'settings') return 'settings';
  return 'home';
};

const tabToPath = (tab: NavigationTab): string => {
  if (tab === 'home') return '/';
  return `/${tab}`;
};

export const AppShell: React.FC = () => {
  const [activeTab, setActiveTab] = useState<NavigationTab>(() => {
    if (typeof window !== 'undefined') {
      return pathToTab(window.location.pathname);
    }
    return 'home';
  });

  const navigateTo = useCallback((tab: NavigationTab) => {
    setActiveTab(tab);
    if (typeof window !== 'undefined') {
      const newPath = tabToPath(tab);
      if (window.location.pathname !== newPath) {
        window.history.pushState({ tab }, '', newPath);
      }
    }
  }, []);

  useEffect(() => {
    const handlePopState = () => {
      setActiveTab(pathToTab(window.location.pathname));
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Keyboard shortcut: Press 'S' to toggle or trigger study session
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Do not trigger if typing in an input
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) {
        return;
      }

      if (e.key === 's' || e.key === 'S') {
        const primaryBtn = document.getElementById('btn-start-study-session');
        if (primaryBtn) {
          primaryBtn.click();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div className="sfm-app-shell">
      <Sidebar activeTab={activeTab} onNavigate={navigateTo} />
      <main className="sfm-main-content" id="main-content-area" tabIndex={-1}>
        {activeTab === 'home' && <HomePage data={mockHomeData} />}
        {activeTab === 'analytics' && <AnalyticsPage data={mockAnalyticsData} />}
        {activeTab === 'sessions' && <SessionsPage data={mockSessionsData} />}
        {activeTab === 'settings' && <SettingsPage data={mockSettingsData} />}
      </main>
    </div>
  );
};
