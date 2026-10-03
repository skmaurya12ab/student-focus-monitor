import React from 'react';
import { NavigationTab } from '../../types/dashboard';
import {
  BrandAtIcon,
  HomeNavIcon,
  AnalyticsNavIcon,
  SessionsNavIcon,
  SettingsNavIcon,
  GearIcon,
} from '../common/Icons';

interface SidebarProps {
  activeTab: NavigationTab;
  onNavigate: (tab: NavigationTab) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, onNavigate }) => {
  const navItems: Array<{
    id: NavigationTab;
    label: string;
    icon: React.ReactNode;
    activeIcon: React.ReactNode;
  }> = [
    {
      id: 'home',
      label: 'Home / Live Dashboard',
      icon: <HomeNavIcon size={20} color="#171A24" />,
      activeIcon: <HomeNavIcon size={20} color="#8E909B" />,
    },
    {
      id: 'analytics',
      label: 'Focus Analytics',
      icon: <AnalyticsNavIcon size={20} color="#171A24" />,
      activeIcon: <AnalyticsNavIcon size={20} color="#8E909B" />,
    },
    {
      id: 'sessions',
      label: 'Sessions History',
      icon: <SessionsNavIcon size={20} color="#171A24" />,
      activeIcon: <SessionsNavIcon size={20} color="#8E909B" />,
    },
    {
      id: 'settings',
      label: 'Settings',
      icon: <SettingsNavIcon size={20} color="#171A24" />,
      activeIcon: <SettingsNavIcon size={20} color="#8E909B" />,
    },
  ];

  return (
    <aside className="sfm-sidebar" aria-label="Main Navigation">
      <div className="sfm-sidebar-top">
        <button
          type="button"
          className="sfm-brand-btn"
          onClick={() => onNavigate('home')}
          aria-label="Student Focus Monitor Home"
          title="Student Focus Monitor"
        >
          <BrandAtIcon size={30} />
        </button>
      </div>

      <nav className="sfm-sidebar-nav">
        {navItems.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              className={`sfm-nav-item ${isActive ? 'is-active' : 'is-inactive'}`}
              onClick={() => onNavigate(item.id)}
              aria-label={item.label}
              title={item.label}
              aria-current={isActive ? 'page' : undefined}
            >
              <div className="sfm-nav-icon-container">
                {isActive ? item.activeIcon : item.icon}
              </div>
            </button>
          );
        })}
      </nav>

      <div className="sfm-sidebar-bottom">
        <button
          type="button"
          className="sfm-gear-btn"
          onClick={() => onNavigate('settings')}
          aria-label="Settings configuration"
          title="Settings"
        >
          <div className="sfm-gear-circle">
            <GearIcon size={20} color="#171A24" />
          </div>
        </button>
      </div>
    </aside>
  );
};
