import React, { useEffect, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, MessageSquare, ClipboardCheck, User, BookOpen,
  Users, Activity, Plug, BarChart3, ChevronLeft, ChevronRight,
  Sparkles, Zap, Map, Settings, X, Lock
} from 'lucide-react';
import { PROFILE_GATE_ALLOWED, useAuth } from '../../contexts/useAuth';

interface NavItem {
  label: string;
  path: string;
  icon: React.ReactNode;
  badge?: number;
}

// Employee Navigation
const employeeMainNav: NavItem[] = [
  { label: 'Dashboard', path: '/app/dashboard', icon: <LayoutDashboard size={20} /> },
  { label: 'AI Chat', path: '/app/chat', icon: <MessageSquare size={20} /> },
  { label: 'Checklist', path: '/app/checklist', icon: <ClipboardCheck size={20} /> },
  { label: 'Profile', path: '/app/profile', icon: <User size={20} /> },
  { label: 'Roadmap', path: '/app/roadmap', icon: <Map size={20} /> },
];

const employeeResourceNav: NavItem[] = [
  { label: 'Knowledge Base', path: '/app/knowledge', icon: <BookOpen size={20} /> },
  { label: 'Timeline', path: '/app/timeline', icon: <Activity size={20} /> },
  { label: 'Integrations', path: '/app/integrations', icon: <Plug size={20} /> },
];

// HR Admin Navigation
const hrManagementNav: NavItem[] = [
  { label: 'HR Dashboard', path: '/app/admin', icon: <Users size={20} /> },
  { label: 'Analytics', path: '/app/analytics', icon: <BarChart3 size={20} /> },
];

const hrPlatformNav: NavItem[] = [
  { label: 'Knowledge Base', path: '/app/knowledge', icon: <BookOpen size={20} /> },
  { label: 'Integrations', path: '/app/integrations', icon: <Plug size={20} /> },
];

const settingsNav: NavItem[] = [
  { label: 'Settings', path: '/app/settings', icon: <Settings size={20} /> },
];

const COLLAPSED_KEY = 'sidebar-collapsed';

const readCollapsed = () => {
  try {
    return localStorage.getItem(COLLAPSED_KEY) === 'true';
  } catch {
    return false;
  }
};

interface SidebarProps {
  /** Drawer state below the lg breakpoint; ignored on desktop. */
  mobileOpen: boolean;
  onMobileClose: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ mobileOpen, onMobileClose }) => {
  const [desktopCollapsed, setDesktopCollapsed] = useState(readCollapsed);
  const { isAdmin, needsProfile } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  // The mobile drawer always shows labels, even if the desktop rail is collapsed.
  const collapsed = desktopCollapsed && !mobileOpen;

  const toggleCollapsed = () => {
    setDesktopCollapsed(prev => {
      try {
        localStorage.setItem(COLLAPSED_KEY, String(!prev));
      } catch {
        // Storage can be unavailable (private mode); the toggle still works for this visit.
      }
      return !prev;
    });
  };

  useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onMobileClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [mobileOpen, onMobileClose]);

  const linkClasses = (isActive: boolean) =>
    `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 group relative ${
      isActive
        ? 'bg-primary-600/20 text-primary-400 font-semibold'
        : 'text-(--text-sidebar) hover:bg-(--bg-sidebar-hover) hover:text-(--text-sidebar-active)'
    }`;

  const renderNavGroup = (title: string, items: NavItem[]) => (
    <div className="mb-6">
      {!collapsed && (
        <p className="px-3 mb-2 text-[11px] font-semibold uppercase tracking-wider text-(--text-tertiary)">
          {title}
        </p>
      )}
      <nav className="flex flex-col gap-0.5">
        {items.map(item => needsProfile && !PROFILE_GATE_ALLOWED.includes(item.path) ? (
          <span
            key={item.path}
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-(--text-sidebar) opacity-45 cursor-not-allowed select-none"
            title="Complete your profile to unlock"
            aria-disabled="true"
          >
            <span className="shrink-0">{item.icon}</span>
            {!collapsed && <span className="truncate">{item.label}</span>}
            {!collapsed && <Lock size={13} className="ml-auto shrink-0" />}
          </span>
        ) : (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) => linkClasses(isActive)}
            title={collapsed ? item.label : undefined}
            aria-label={collapsed ? item.label : undefined}
            onClick={onMobileClose}
          >
            <span className="shrink-0">{item.icon}</span>
            {!collapsed && <span className="truncate">{item.label}</span>}
            {item.badge && !collapsed && (
              <span className="ml-auto bg-primary-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                {item.badge}
              </span>
            )}
            {location.pathname === item.path && (
              <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-primary-500 rounded-r-full" />
            )}
          </NavLink>
        ))}
      </nav>
    </div>
  );

  return (
    <>
    {/* Backdrop for the mobile drawer */}
    <div
      className={`fixed inset-0 z-40 bg-black/50 backdrop-blur-[2px] transition-opacity duration-300 lg:hidden ${
        mobileOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
      }`}
      onClick={onMobileClose}
      aria-hidden="true"
    />
    <aside
      className={`fixed inset-y-0 left-0 z-50 w-[272px] max-w-[85vw] lg:static lg:z-auto lg:max-w-none h-dvh shrink-0 bg-(--bg-sidebar) flex flex-col border-r border-(--border-default) transition-[width,transform] duration-300 ${
        mobileOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full'
      } lg:translate-x-0 lg:shadow-none ${collapsed ? 'lg:w-[68px]' : 'lg:w-[240px]'}`}
      aria-label="Main navigation"
    >
      {/* Logo */}
      <div className="h-14 flex items-center justify-between px-4 border-b border-white/5 shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-linear-to-br from-primary-500 to-accent-500 flex items-center justify-center shadow-xs">
            <Zap size={18} className="text-white" />
          </div>
          {!collapsed && (
            <div className="animate-fade-in">
              <h1 className="text-sm font-bold text-white tracking-tight">NovaByte</h1>
              <p className="text-[10px] text-surface-400 font-medium">
                {isAdmin ? 'HR Admin Suite' : 'Developer Onboarding'}
              </p>
            </div>
          )}
        </div>
        <button
          onClick={onMobileClose}
          className="lg:hidden p-1.5 rounded-lg text-(--text-sidebar) hover:bg-(--bg-sidebar-hover) transition-colors cursor-pointer"
          aria-label="Close navigation"
        >
          <X size={18} />
        </button>
      </div>

      {/* Navigation */}
      <div className="flex-1 overflow-y-auto scrollbar-thin px-2 py-4">
        {isAdmin ? (
          <>
            {renderNavGroup('HR Operations', hrManagementNav)}
            {renderNavGroup('Platform & Resources', hrPlatformNav)}
            {renderNavGroup('System', settingsNav)}
          </>
        ) : (
          <>
            {renderNavGroup('Main', employeeMainNav)}
            {renderNavGroup('Resources', employeeResourceNav)}
            {renderNavGroup('System', settingsNav)}
          </>
        )}
      </div>

      {/* AI Assistant Quick Access (employees only) */}
      {!collapsed && !needsProfile && !isAdmin && (
        <div className="px-3 pb-3">
          <button
            onClick={() => {
              onMobileClose();
              navigate('/app/chat');
            }}
            className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg bg-linear-to-r from-primary-600/20 to-accent-600/20 border border-primary-500/20 text-primary-300 text-sm font-medium hover:from-primary-600/30 hover:to-accent-600/30 transition-all cursor-pointer shadow-xs"
          >
            <Sparkles size={16} />
            <span>AI Assistant</span>
          </button>
        </div>
      )}

      {/* Collapse Toggle (desktop only) */}
      <div className="hidden lg:block p-3 border-t border-white/5 shrink-0">
        <button
          onClick={toggleCollapsed}
          className="w-full flex items-center justify-center p-2 rounded-lg text-(--text-sidebar) hover:bg-(--bg-sidebar-hover) transition-colors cursor-pointer"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>
    </aside>
    </>
  );
};
