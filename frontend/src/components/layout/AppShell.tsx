import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { NavigationTab } from '../../types/dashboard';
import { Sidebar } from './Sidebar';
import { HomePage } from '../../features/home/HomePage';
import { AnalyticsPage } from '../../features/analytics/AnalyticsPage';
import { SessionsPage } from '../../features/sessions/SessionsPage';
import { SettingsPage } from '../../features/settings/SettingsPage';
import { AccountPage } from '../../features/account/AccountPage';
import { useAuth } from '../../context/AuthContext';
import {
  mockHomeData,
  mockSettingsData,
} from '../../data/mock';

const pathToTab = (path: string): NavigationTab => {
  const normalized = path.replace(/^\/|\/$/g, '').toLowerCase();
  if (normalized === 'analytics') return 'analytics';
  if (normalized === 'sessions') return 'sessions';
  if (normalized === 'settings') return 'settings';
  if (normalized === 'account') return 'account';
  return 'home';
};

const tabToPath = (tab: NavigationTab): string => {
  if (tab === 'home') return '/';
  return `/${tab}`;
};

export const AppShell: React.FC = () => {
  const { user } = useAuth();
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

  // Global listener: Clicking profile shortcut badge in header navigates to Account page
  useEffect(() => {
    const handleProfileShortcut = (e: MouseEvent) => {
      const target = (e.target as HTMLElement)?.closest('.sfm-profile-shortcut-badge');
      if (target) {
        e.preventDefault();
        navigateTo('account');
      }
    };
    document.addEventListener('click', handleProfileShortcut);
    return () => document.removeEventListener('click', handleProfileShortcut);
  }, [navigateTo]);

  // Keyboard shortcut: Press 'S' to toggle or trigger study session
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
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

  const homeData = useMemo(() => {
    if (!user) return mockHomeData;
    const firstName = user.displayName.split(' ')[0] || user.displayName;
    return {
      ...mockHomeData,
      userName: user.displayName,
      greetingTitle: `Hi ${firstName}, Ready to Focus and Achieve?`,
    };
  }, [user]);

  return (
    <div className="sfm-app-shell">
      <Sidebar activeTab={activeTab} onNavigate={navigateTo} />
      <main className="sfm-main-content" id="main-content-area" tabIndex={-1}>
        {activeTab === 'home' && <HomePage data={homeData} />}
        {activeTab === 'analytics' && <AnalyticsPage />}
        {activeTab === 'sessions' && <SessionsPage />}
        {activeTab === 'settings' && (
          <SettingsPage
            data={mockSettingsData}
            onNavigateToAccount={() => navigateTo('account')}
          />
        )}
        {activeTab === 'account' && <AccountPage />}
      </main>
    </div>
  );
};

