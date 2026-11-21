import React, { useState, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Users, Search, Filter, TrendingUp, Clock, CheckCircle2,
  RefreshCw
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { api } from '../services/api';
import { useAuth } from '../contexts/useAuth';
import { useLiveRefresh } from '../hooks/useLiveRefresh';
import type { OnboardingSession } from '../types';
import { InviteEmployeeModal } from '../components/admin/InviteEmployeeModal';
import { PendingInvitesPanel } from '../components/admin/PendingInvitesPanel';

export const AdminDashboardPage: React.FC = () => {
  const [sessions, setSessions] = useState<OnboardingSession[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  const [isInviteOpen, setIsInviteOpen] = useState(false);
  const [invitesVersion, setInvitesVersion] = useState(0);
  const navigate = useNavigate();
  const { user } = useAuth();

  const loadSessions = useCallback(async (showRefreshing = false) => {
    if (showRefreshing) setIsRefreshing(true);
    try {
      const data = await api.getSessions();
      setSessions(data);
    } catch (e) {
      console.error('Failed to load onboarding sessions:', e);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  // Employees' progress changes as they work, so keep the list current while HR has it open.
  const refreshSessions = useCallback(() => loadSessions(), [loadSessions]);
  useLiveRefresh(refreshSessions, 10000);

  const completedCount = sessions.filter(s => s.status === 'Completed').length;
  const inProgressCount = sessions.filter(s => s.status !== 'Completed').length;
  const averageProgress = sessions.length > 0
    ? Math.round(sessions.reduce((sum, s) => sum + (s.progress ?? 0), 0) / sessions.length)
    : 0;

  const filtered = sessions.filter(s => {
    if (statusFilter !== 'All') {
      if (statusFilter === 'In Progress') {
        if (s.status !== 'In Progress' && s.status !== 'Not Started') return false;
      } else if (s.status !== statusFilter) {
        return false;
      }
    }
    if (search) {
      const q = search.toLowerCase();
      return (
        (s.employee_email || '').toLowerCase().includes(q) ||
        (s.employee_name || '').toLowerCase().includes(q) ||
        (s.employee_role || '').toLowerCase().includes(q) ||
        (s.session_id || '').toLowerCase().includes(q) ||
        (s.persona_match || '').toLowerCase().includes(q)
      );
    }
    return true;
  });

  if (isLoading) {
    return (
      <div className="p-4 sm:p-8 space-y-4">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">{[1,2,3,4].map(i => <div key={i} className="skeleton h-28" />)}</div>
        <div className="skeleton h-96" />
      </div>
    );
  }

  return (
    <div className="px-4 py-5 sm:p-6 md:p-8 max-w-7xl mx-auto animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 sm:mb-8">
        <div>
          <h1 className="text-2xl font-bold text-(--text-primary) flex items-center gap-2">
            <Users size={24} className="text-primary-500" /> HR Admin Dashboard
          </h1>
          <p className="text-(--text-secondary) mt-1">
            Live progress for every developer onboarding{user?.username && <> · Signed in as <span className="font-medium text-(--text-primary)">{user.username}</span></>}
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={() => loadSessions(true)}
            disabled={isRefreshing}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg border border-(--border-default) bg-(--bg-card) text-(--text-primary) text-sm font-medium hover:bg-(--bg-secondary) transition-colors"
            title="Refresh sessions now"
          >
            <RefreshCw size={15} className={isRefreshing ? 'animate-spin text-primary-500' : ''} />
            <span>{isRefreshing ? 'Refreshing...' : 'Refresh'}</span>
          </button>
          <button
            onClick={() => setIsInviteOpen(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors shadow-sm whitespace-nowrap cursor-pointer"
          >
            + New Onboarding
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-8">
        {[
          { label: 'Total Sessions', value: sessions.length, icon: <Users size={20} />, color: 'from-blue-500 to-blue-600' },
          { label: 'Active & In Progress', value: inProgressCount, icon: <Clock size={20} />, color: 'from-amber-500 to-orange-500' },
          { label: 'Completed', value: completedCount, icon: <CheckCircle2 size={20} />, color: 'from-green-500 to-emerald-600' },
          { label: 'Average Progress', value: `${averageProgress}%`, icon: <TrendingUp size={20} />, color: 'from-purple-500 to-purple-600' },
        ].map(stat => (
          <div key={stat.label} className="bg-(--bg-card) border border-(--border-default) rounded-xl p-4 sm:p-5 shadow-xs min-w-0">
            <div className={`inline-flex p-2.5 rounded-lg bg-linear-to-br ${stat.color} text-white mb-3`}>{stat.icon}</div>
            <p className="text-xl sm:text-2xl font-bold text-(--text-primary)">{stat.value}</p>
            <p className="text-xs sm:text-sm text-(--text-secondary)">{stat.label}</p>
          </div>
        ))}
      </div>

      <PendingInvitesPanel
        version={invitesVersion}
        onChanged={() => loadSessions(true)}
      />

      {/* Filters + Table */}
      <div className="bg-(--bg-card) border border-(--border-default) rounded-xl overflow-hidden shadow-xs">
        <div className="p-4 border-b border-(--border-default) flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-(--text-tertiary)" />
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search by employee email, persona, or session ID..."
              className="w-full pl-9 pr-4 py-2 rounded-lg border border-(--border-default) bg-(--bg-secondary) text-sm text-(--text-primary) focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <div className="relative">
            <Filter size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-(--text-tertiary)" />
            <select
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value)}
              className="pl-9 pr-8 py-2 rounded-lg border border-(--border-default) bg-(--bg-secondary) text-sm text-(--text-primary) appearance-none focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="All">All Statuses</option>
              <option value="In Progress">In Progress / Active</option>
              <option value="Completed">Completed</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr className="border-b border-(--border-default) bg-(--bg-secondary)/50">
                {['Employee', 'Role', 'Progress', 'Phase', 'Status', 'Last active'].map(h => (
                  <th key={h} className="px-6 py-3 text-left text-xs font-semibold text-(--text-tertiary) uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map(session => (
                <tr key={session.session_id} onClick={() => navigate(`/app/admin/employees/${encodeURIComponent(session.session_id)}`)}
                  className="border-b border-(--border-subtle) hover:bg-(--bg-secondary) transition-colors cursor-pointer">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-full bg-linear-to-br from-primary-500 to-indigo-600 flex items-center justify-center text-white text-sm font-bold shadow-xs">
                        {(session.employee_name || session.employee_email || 'U').charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <Link
                          to={`/app/admin/employees/${encodeURIComponent(session.session_id)}`}
                          onClick={e => e.stopPropagation()}
                          className="text-sm font-semibold text-(--text-primary) hover:text-primary-500 hover:underline"
                        >
                          {session.employee_name || (session.employee_email || 'User').split('@')[0]}
                        </Link>
                        <p className="text-xs text-(--text-tertiary)">{session.employee_email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm">
                    <p className="text-(--text-primary) font-medium">{session.employee_role || 'Profile incomplete'}</p>
                    {session.persona_match && <p className="text-xs text-(--text-tertiary)">{session.persona_match}</p>}
                  </td>
                  <td className="px-6 py-4 min-w-36">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 rounded-full bg-(--bg-tertiary) overflow-hidden" role="progressbar"
                        aria-valuenow={Math.round(session.progress ?? 0)} aria-valuemin={0} aria-valuemax={100}
                        aria-label={`${session.employee_name || session.employee_email} progress`}>
                        <div className="h-full rounded-full bg-primary-500" style={{ width: `${session.progress ?? 0}%` }} />
                      </div>
                      <span className="text-xs font-semibold text-(--text-primary) w-9 text-right">{Math.round(session.progress ?? 0)}%</span>
                    </div>
                    <p className="text-xs text-(--text-tertiary) mt-1">
                      {session.total_tasks ? `${session.completed_tasks}/${session.total_tasks} tasks` : 'No plan yet'}
                    </p>
                  </td>
                  <td className="px-6 py-4 text-sm text-(--text-secondary) capitalize">
                    {(session.current_phase || 'greeting').replace('_', ' ')}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                      session.status === 'Completed'
                        ? 'bg-green-500/10 text-green-500 border border-green-500/20'
                        : session.status === 'In Progress'
                        ? 'bg-blue-500/10 text-blue-500 border border-blue-500/20'
                        : 'bg-amber-500/10 text-amber-500 border border-amber-500/20'
                    }`}>
                      {session.status || 'In Progress'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-(--text-secondary) whitespace-nowrap">
                    {session.last_activity_at
                      ? formatDistanceToNow(new Date(session.last_activity_at), { addSuffix: true })
                      : <span className="text-(--text-tertiary)">Not yet</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {filtered.length === 0 && (
          <div className="text-center py-16">
            <Users size={48} className="text-(--text-tertiary) mx-auto mb-3" />
            <p className="text-(--text-primary) font-medium">No sessions found</p>
            <p className="text-xs text-(--text-tertiary) mt-1">Sessions will appear here automatically when employees start onboarding</p>
          </div>
        )}
      </div>

      <InviteEmployeeModal
        isOpen={isInviteOpen}
        onClose={() => setIsInviteOpen(false)}
        onInvited={() => { loadSessions(true); setInvitesVersion(v => v + 1); }}
      />
    </div>
  );
};
