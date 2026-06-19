import React, { useState } from 'react';
import { Brand } from '../../components/Brand/Brand';
import { StatusDot } from '../../components/StatusDot/StatusDot';
import { ThemeToggle } from '../../components/ThemeToggle/ThemeToggle';
import { Tabs } from '../../components/Tabs/Tabs';

const APP_TABS = [
  { key: 'add',      num: '01', label: 'add'      },
  { key: 'jobs',     num: '02', label: 'jobs'     },
  { key: 'library',  num: '03', label: 'library'  },
  { key: 'settings', num: '04', label: 'settings' },
];

export interface AppShellProps {
  version?: string;
  workerActive?: boolean;
  /** Tab key → panel content */
  panels: Record<string, React.ReactNode>;
  initialTab?: string;
}

export function AppShell({ version = '1.0.0', workerActive = false, panels, initialTab = 'add' }: AppShellProps) {
  const [active, setActive] = useState(initialTab);
  const [theme, setTheme] = useState<'light' | 'dark'>('light');

  const toggleTheme = () => {
    const next = theme === 'light' ? 'dark' : 'light';
    setTheme(next);
    document.documentElement.setAttribute('data-theme', next);
  };

  return (
    <div className="shell">
      <header className="app-bar">
        <Brand version={version} />
        <div className="app-bar__right">
          <StatusDot active={workerActive} />
          <ThemeToggle onClick={toggleTheme} />
        </div>
      </header>

      <Tabs items={APP_TABS} active={active} onChange={setActive} />

      {APP_TABS.map(tab => (
        <div
          key={tab.key}
          className={`tab-panel${active === tab.key ? ' tab-panel--active' : ''}`}
          role="tabpanel"
        >
          {panels[tab.key]}
        </div>
      ))}
    </div>
  );
}
