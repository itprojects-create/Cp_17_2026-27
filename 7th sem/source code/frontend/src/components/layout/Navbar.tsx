import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Bell, Moon, Sun, Search, ChevronRight, Settings, LogOut, Menu, CornerDownLeft } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { useTheme } from '../../contexts/useTheme';
import { useAuth } from '../../contexts/useAuth';
import { api } from '../../services/api';
import type { AgentActivityItem } from '../../types';

const breadcrumbMap: Record<string, string> = {
  '/app/dashboard': 'Dashboard',
  '/app/chat': 'AI Chat',
  '/app/checklist': 'Checklist',
  '/app/profile': 'Profile Setup',
  '/app/knowledge': 'Knowledge Base',
  '/app/admin': 'HR Dashboard',
  '/app/timeline': 'Timeline',
  '/app/integrations': 'Integrations',
  '/app/analytics': 'Analytics',
  '/app/settings': 'Settings',
  '/app/roadmap': 'Onboarding Roadmap',
};

// Pages each role can open; mirrors the route guards in App.tsx.
const EMPLOYEE_PAGES = [
  '/app/dashboard', '/app/chat', '/app/checklist', '/app/profile', '/app/roadmap',
  '/app/knowledge', '/app/timeline', '/app/integrations', '/app/settings',
];
const ADMIN_PAGES = ['/app/admin', '/app/analytics', '/app/knowledge', '/app/integrations', '/app/settings'];

const SEEN_KEY = 'notifications-seen-at';

const readSeenAt = () => {
  try {
    return Number(localStorage.getItem(SEEN_KEY)) || 0;
  } catch {
    return 0;
  }
};

// The backend stores UTC timestamps; SQLite drops the offset, so treat bare ones as UTC.
const parseTimestamp = (ts?: string) => {
  if (!ts) return null;
  const date = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(ts) ? ts : `${ts}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
};

interface NavbarProps {
  onMenuClick: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onMenuClick }) => {
  const { theme, toggleTheme } = useTheme();
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const [query, setQuery] = useState('');
  const [activities, setActivities] = useState<AgentActivityItem[]>([]);
  const [activitiesLoaded, setActivitiesLoaded] = useState(false);
  const [seenAt, setSeenAt] = useState(readSeenAt);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const notifRef = useRef<HTMLDivElement>(null);

  const currentPage = breadcrumbMap[location.pathname]
    || (location.pathname.startsWith('/app/admin/employees/') ? 'Employee Details' : 'Dashboard');
  const userLabel = (user?.username || user?.email || 'User').trim();
  const userInitial = userLabel.charAt(0).toUpperCase();

  const pageMatches = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (isAdmin ? ADMIN_PAGES : EMPLOYEE_PAGES)
      .map(path => ({ path, label: breadcrumbMap[path] }))
      .filter(p => !q || p.label.toLowerCase().includes(q));
  }, [query, isAdmin]);

  const loadActivities = useCallback(async () => {
    // HR admins see every session, so a single employee's agent activity isn't theirs to be notified about.
    if (isAdmin) {
      setActivitiesLoaded(true);
      return;
    }
    try {
      const sessions = await api.getSessions();
      if (sessions?.length) {
        const items: AgentActivityItem[] = await api.getActivity(sessions[0].session_id);
        setActivities([...items].reverse().slice(0, 8));
      }
    } catch {
      // Notifications are non-essential; keep whatever was shown before.
    } finally {
      setActivitiesLoaded(true);
    }
  }, [isAdmin]);

  useEffect(() => {
    void loadActivities();
  }, [loadActivities]);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) setShowUserMenu(false);
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) setShowNotifications(false);
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setShowUserMenu(false);
        setShowNotifications(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, []);

  const unreadCount = activities.filter(a => (parseTimestamp(a.timestamp)?.getTime() ?? 0) > seenAt).length;

  const markAllRead = () => {
    const now = Date.now();
    setSeenAt(now);
    try {
      localStorage.setItem(SEEN_KEY, String(now));
    } catch {
      // Without storage the badge simply reappears next visit.
    }
  };

  const toggleNotifications = () => {
    const opening = !showNotifications;
    setShowNotifications(opening);
    setShowUserMenu(false);
    if (opening) void loadActivities();
  };

  const closeSearch = () => {
    setShowSearch(false);
    setQuery('');
  };

  const goTo = (path: string) => {
    closeSearch();
    navigate(path);
  };

  const iconButton = 'p-2 rounded-lg text-(--text-secondary) hover:bg-(--bg-tertiary) hover:text-(--text-primary) transition-colors cursor-pointer';

  return (
    <header className="h-14 flex items-center justify-between gap-2 px-3 sm:px-6 border-b border-(--border-default) bg-(--bg-primary)/90 backdrop-blur-md shrink-0 z-30">
      <div className="flex items-center gap-1 min-w-0">
        <button onClick={onMenuClick} className={`${iconButton} lg:hidden -ml-1`} aria-label="Open navigation">
          <Menu size={20} />
        </button>

        {/* Breadcrumb */}
        <nav className="flex items-center gap-2 text-sm min-w-0" aria-label="Breadcrumb">
          <span className="hidden sm:inline text-(--text-tertiary)">Home</span>
          <ChevronRight size={14} className="hidden sm:block text-(--text-tertiary) shrink-0" />
          <span className="font-semibold text-(--text-primary) truncate">{currentPage}</span>
        </nav>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-0.5 sm:gap-1 shrink-0">
        {/* Page search */}
        <div className="relative">
          {showSearch && (
            // Phones: span the header; from sm up: anchor beside the search button.
            <div className="fixed inset-x-3 top-2 sm:absolute sm:inset-x-auto sm:top-1/2 sm:right-10 sm:-translate-y-1/2 sm:w-72 animate-fade-in z-50">
              <input
                type="text"
                placeholder="Jump to page..."
                autoFocus
                value={query}
                onChange={e => setQuery(e.target.value)}
                onBlur={closeSearch}
                onKeyDown={e => {
                  if (e.key === 'Enter' && pageMatches[0]) goTo(pageMatches[0].path);
                  if (e.key === 'Escape') closeSearch();
                }}
                aria-label="Jump to page"
                className="w-full px-3 py-1.5 rounded-lg border border-(--border-default) bg-(--bg-secondary) text-sm text-(--text-primary) placeholder:text-(--text-tertiary) focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              <div className="absolute left-0 right-0 top-full mt-2 bg-(--bg-card) border border-(--border-default) rounded-xl shadow-lg overflow-hidden py-1">
                {pageMatches.length === 0 ? (
                  <p className="px-3 py-2 text-sm text-(--text-tertiary)">No matching pages</p>
                ) : (
                  pageMatches.map((p, i) => (
                    <button
                      key={p.path}
                      // mousedown fires before the input's blur, so the click isn't lost.
                      onMouseDown={e => {
                        e.preventDefault();
                        goTo(p.path);
                      }}
                      className={`w-full flex items-center justify-between px-3 py-2 text-sm text-left transition-colors cursor-pointer ${
                        i === 0 ? 'bg-(--bg-secondary) text-(--text-primary)' : 'text-(--text-secondary) hover:bg-(--bg-secondary)'
                      }`}
                    >
                      {p.label}
                      {i === 0 && <CornerDownLeft size={14} className="text-(--text-tertiary)" />}
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
          <button
            onClick={() => (showSearch ? closeSearch() : setShowSearch(true))}
            className={iconButton}
            aria-label="Search pages"
          >
            <Search size={18} />
          </button>
        </div>

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className={iconButton}
          title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
        >
          {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
        </button>

        {/* Notifications: recent agent activity for the user's onboarding session */}
        <div className="relative" ref={notifRef}>
          <button
            onClick={toggleNotifications}
            className={`${iconButton} relative`}
            aria-label={unreadCount ? `Notifications (${unreadCount} new)` : 'Notifications'}
            aria-expanded={showNotifications}
          >
            <Bell size={18} />
            {unreadCount > 0 && (
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full ring-2 ring-(--bg-primary)" />
            )}
          </button>
          {showNotifications && (
            <div className="absolute -right-12 sm:right-0 top-11 w-[min(20rem,calc(100vw-1.5rem))] bg-(--bg-card) border border-(--border-default) rounded-xl shadow-lg overflow-hidden animate-fade-in z-50">
              <div className="px-4 py-3 border-b border-(--border-default) flex items-center justify-between">
                <h3 className="text-sm font-semibold text-(--text-primary)">Notifications</h3>
                {unreadCount > 0 && (
                  <button onClick={markAllRead} className="text-xs text-primary-500 hover:text-primary-400 cursor-pointer">
                    Mark all read
                  </button>
                )}
              </div>
              <div className="max-h-72 overflow-y-auto scrollbar-thin">
                {!activitiesLoaded ? (
                  <div className="p-4 space-y-3">
                    <div className="skeleton h-4 w-3/4" />
                    <div className="skeleton h-4 w-1/2" />
                  </div>
                ) : activities.length === 0 ? (
                  <div className="px-4 py-8 text-center">
                    <Bell size={20} className="mx-auto mb-2 text-(--text-tertiary)" />
                    <p className="text-sm text-(--text-secondary)">You're all caught up</p>
                    <p className="text-xs text-(--text-tertiary) mt-1">Agent updates about your onboarding will appear here.</p>
                  </div>
                ) : (
                  activities.map(a => {
                    const ts = parseTimestamp(a.timestamp);
                    const unread = (ts?.getTime() ?? 0) > seenAt;
                    return (
                      <div
                        key={a.id}
                        className={`px-4 py-3 border-l-2 ${unread ? 'border-primary-500 bg-primary-500/5' : 'border-transparent'}`}
                      >
                        <p className="text-sm text-(--text-primary)">{a.label}</p>
                        {a.details && <p className="text-xs text-(--text-secondary) mt-0.5 line-clamp-2">{a.details}</p>}
                        {ts && (
                          <p className="text-xs text-(--text-tertiary) mt-1">{formatDistanceToNow(ts, { addSuffix: true })}</p>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}
        </div>

        {/* User Menu */}
        <div className="relative ml-1 sm:ml-2" ref={userMenuRef}>
          <button
            onClick={() => {
              setShowUserMenu(!showUserMenu);
              setShowNotifications(false);
            }}
            className="flex items-center gap-2 p-1 rounded-lg hover:bg-(--bg-tertiary) transition-colors cursor-pointer"
            aria-label="Account menu"
            aria-expanded={showUserMenu}
          >
            <div className="w-8 h-8 rounded-full bg-linear-to-br from-primary-500 to-accent-500 flex items-center justify-center text-white text-sm font-bold">
              {userInitial}
            </div>
          </button>
          {showUserMenu && (
            <div className="absolute right-0 top-11 w-56 bg-(--bg-card) border border-(--border-default) rounded-xl shadow-lg overflow-hidden animate-fade-in z-50">
              <div className="px-4 py-3 border-b border-(--border-default)">
                <p className="text-sm font-semibold text-(--text-primary) truncate">{user?.username || 'Developer'}</p>
                <p className="text-xs text-(--text-tertiary) truncate">{user?.email}</p>
              </div>
              <div className="py-1">
                {[
                  {
                    icon: <Settings size={16} />,
                    label: 'Settings',
                    action: () => {
                      setShowUserMenu(false);
                      navigate('/app/settings');
                    },
                  },
                  {
                    icon: <LogOut size={16} />,
                    label: 'Sign Out',
                    action: () => {
                      setShowUserMenu(false);
                      logout();
                    },
                  },
                ].map(item => (
                  <button
                    key={item.label}
                    onClick={item.action}
                    className="w-full flex items-center gap-2.5 px-4 py-2 text-sm text-(--text-secondary) hover:bg-(--bg-secondary) hover:text-(--text-primary) transition-colors cursor-pointer"
                  >
                    {item.icon}
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
