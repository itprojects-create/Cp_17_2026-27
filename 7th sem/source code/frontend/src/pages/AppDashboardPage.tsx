import React, { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Sparkles, ArrowRight, CheckCircle2, Clock, AlertCircle,
  MessageSquare, TrendingUp, Target, Zap, Briefcase
} from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../contexts/useAuth';
import { useLiveRefresh } from '../hooks/useLiveRefresh';
import type { OnboardingSession, ProgressData, ChecklistItemType } from '../types';

type Profile = Awaited<ReturnType<typeof api.getProfile>>;

// The agent's phases (backend/app/agent/graph.py), in the order an employee moves through them.
const PHASES: { label: string; matches: string[] }[] = [
  { label: 'Getting started', matches: ['greeting', 'collect_info'] },
  { label: 'Onboarding tasks', matches: ['onboarding'] },
  { label: 'First contribution', matches: ['first_task'] },
  { label: 'Completed', matches: ['completed'] },
];
const phaseIndex = (phase?: string | null, status?: string) =>
  status === 'Completed' ? PHASES.length - 1 : Math.max(0, PHASES.findIndex(p => p.matches.includes(phase || 'greeting')));

export const AppDashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [sessions, setSessions] = useState<OnboardingSession[]>([]);
  const [progress, setProgress] = useState<ProgressData | null>(null);
  const [checklist, setChecklist] = useState<ChecklistItemType[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Re-read on an interval and on tab focus, so progress made in chat, a re-plan after a
  // profile edit, or a name change shows up without a page reload.
  const load = useCallback(async () => {
    try {
      const [s, p] = await Promise.all([api.getSessions(), api.getProfile().catch(() => null)]);
      setSessions(s);
      if (p) setProfile(p);
      if (s.length > 0) {
        const [prog, items] = await Promise.all([api.getProgress(s[0].session_id), api.getChecklist(s[0].session_id)]);
        setProgress(prog);
        setChecklist(items);
      }
      setLoadError(null);
    } catch (e) {
      console.error(e);
      // Keep showing the last good data if a background refresh fails.
      setLoadError(prev => prev ?? (sessions.length ? null : 'Dashboard data is currently unavailable.'));
    } finally {
      setIsLoading(false);
    }
  }, [sessions.length]);
  useLiveRefresh(load, 20000);

  const currentSession = sessions[0];
  const nextTask = checklist.find(c => !['Completed', 'Skipped'].includes(c.status));
  const completedCount = progress?.completed ?? checklist.filter(c => c.status === 'Completed').length;
  const pct = Math.round(progress?.percentage ?? 0);
  const greetingName = profile?.name?.trim() || user?.username || currentSession?.employee_email?.split('@')[0];
  const isAuthoritativelyComplete = currentSession?.status === 'Completed' && pct === 100;
  const currentPhase = phaseIndex(currentSession?.current_phase, currentSession?.status);
  const stack = [...new Set([...(profile?.programming_languages ?? []), ...(profile?.tech_stack ?? [])])];

  if (isLoading) {
    return (
      <div className="p-4 sm:p-8 space-y-6">
        <div className="skeleton h-32 w-full" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          {[1,2,3,4].map(i => <div key={i} className="skeleton h-28" />)}
        </div>
        <div className="skeleton h-64 w-full" />
      </div>
    );
  }

  if (loadError) {
    return <div className="p-8 text-center text-(--text-secondary)">{loadError}<button onClick={() => window.location.reload()} className="ml-2 text-primary-500 underline">Retry</button></div>;
  }

  return (
    <div className="px-4 py-5 sm:p-6 md:p-8 max-w-7xl mx-auto space-y-6 animate-fade-in">
      {/* Welcome Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-linear-to-r from-primary-600 via-primary-500 to-accent-500 p-6 sm:p-8 text-white">
        <div className="absolute top-0 right-0 w-64 h-64 bg-white/5 rounded-full -translate-y-1/2 translate-x-1/4" />
        <div className="absolute bottom-0 left-1/3 w-48 h-48 bg-white/5 rounded-full translate-y-1/2" />
        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles size={20} />
            <span className="text-sm font-medium opacity-90">Welcome back!</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold mb-2 break-words">
            {greetingName ? `Hello, ${greetingName}` : 'Developer Dashboard'}
          </h1>
          <p className="text-white/80 max-w-lg">
            {!currentSession
              ? 'Start your onboarding journey when you are ready.'
              : isAuthoritativelyComplete
                ? 'Your onboarding is complete according to the persisted session record.'
                : `You're ${pct}% through your onboarding journey. Current phase: ${PHASES[currentPhase].label}.`}
          </p>
          {profile?.role && (
            <p className="mt-2 inline-flex flex-wrap items-center gap-x-2 text-sm text-white/90">
              <Briefcase size={14} />
              <span>{profile.role} plan · {profile.years_of_experience} {profile.years_of_experience === 1 ? 'year' : 'years'} experience</span>
              {stack.length > 0 && <span className="text-white/70">· {stack.slice(0, 4).join(', ')}{stack.length > 4 ? ` +${stack.length - 4}` : ''}</span>}
            </p>
          )}
          {currentSession && !isAuthoritativelyComplete && (
            <div className="mt-4 flex items-center gap-4">
              <div className="flex-1 max-w-xs h-2 bg-white/20 rounded-full overflow-hidden">
                <div className="h-full bg-white rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
              </div>
              <span className="text-sm font-bold">{pct}%</span>
            </div>
          )}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        {[
          { label: 'Onboarding Progress', value: `${pct}%`, icon: <TrendingUp size={20} />, color: 'from-blue-500 to-blue-600', sub: `${completedCount}/${checklist.length} tasks` },
          { label: 'Current Phase', value: PHASES[currentPhase].label, icon: <Target size={20} />, color: 'from-purple-500 to-purple-600', sub: `Step ${currentPhase + 1} of ${PHASES.length}` },
          { label: 'Completed Tasks', value: String(completedCount), icon: <CheckCircle2 size={20} />, color: 'from-green-500 to-green-600', sub: 'All time' },
          { label: 'Pending Tasks', value: String(Math.max(0, (progress?.total ?? checklist.length) - completedCount)), icon: <Clock size={20} />, color: 'from-amber-500 to-orange-500', sub: 'Remaining' },
        ].map(stat => (
          <div key={stat.label} className="bg-(--bg-card) border border-(--border-default) rounded-xl p-4 sm:p-5 hover:shadow-md transition-all group min-w-0">
            <div className="flex items-center justify-between mb-3">
              <div className={`p-2.5 rounded-lg bg-linear-to-br ${stat.color} text-white`}>
                {stat.icon}
              </div>
              <span className="text-[11px] sm:text-xs font-medium text-(--text-tertiary) text-right">{stat.sub}</span>
            </div>
            <p className="text-xl sm:text-2xl font-bold text-(--text-primary) truncate capitalize">{stat.value}</p>
            <p className="text-xs sm:text-sm text-(--text-secondary) mt-0.5">{stat.label}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Next Task Recommendation */}
        <div className="lg:col-span-2 bg-(--bg-card) border border-(--border-default) rounded-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-(--border-default) flex items-center gap-2">
            <Zap size={18} className="text-primary-500" />
            <h2 className="font-semibold text-(--text-primary)">Recommended Next Steps</h2>
          </div>
          <div className="p-6">
            {nextTask ? (
              <div className="flex items-start gap-4 p-4 rounded-xl bg-primary-500/5 border border-primary-500/10">
                <div className="p-2 rounded-lg bg-primary-500/10">
                  <AlertCircle size={20} className="text-primary-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-(--text-primary)">{nextTask.task}</h3>
                  <p className="text-sm text-(--text-secondary) mt-1">
                    {nextTask.status === 'Blocked' ? 'Blocked: resolve the prerequisite before continuing.' : `Category: ${nextTask.category}`}
                  </p>
                  <p className="text-xs text-(--text-tertiary) mt-1">Due: {nextTask.deadline || 'No deadline'}</p>
                </div>
                <button
                  onClick={() => navigate('/app/checklist')}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors"
                >
                  Start <ArrowRight size={14} />
                </button>
              </div>
            ) : (
              <div className="text-center py-8">
                <CheckCircle2 size={48} className="text-green-500 mx-auto mb-3" />
                <p className="text-(--text-primary) font-medium">
                  {isAuthoritativelyComplete ? 'Onboarding completed' : checklist.length ? 'No eligible next task' : 'No onboarding tasks yet'}
                </p>
                <p className="text-sm text-(--text-secondary)">
                  {isAuthoritativelyComplete ? 'Your completion is confirmed by the backend.' : 'Complete your profile or start onboarding to receive tasks.'}
                </p>
              </div>
            )}

            {/* Recent tasks */}
            <div className="mt-6 space-y-2">
              {checklist.slice(0, 4).map(item => (
                <div
                  key={item.id}
                  className="flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-(--bg-secondary) transition-colors"
                >
                  <div className={`w-2 h-2 rounded-full shrink-0 ${
                    item.status === 'Completed' ? 'bg-green-500' :
                    item.status === 'In Progress' ? 'bg-blue-500' :
                    item.status === 'Blocked' ? 'bg-red-500' : 'bg-surface-400'
                  }`} />
                  <span className={`text-sm flex-1 ${item.status === 'Completed' ? 'text-(--text-tertiary) line-through' : 'text-(--text-primary)'}`}>
                    {item.task}
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    item.status === 'Completed' ? 'bg-green-500/10 text-green-500' :
                    item.status === 'In Progress' ? 'bg-blue-500/10 text-blue-500' :
                    item.status === 'Blocked' ? 'bg-red-500/10 text-red-500' : 'bg-surface-500/10 text-surface-500'
                  }`}>
                    {item.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Quick Actions Panel */}
        <div className="space-y-4">
          <div className="bg-(--bg-card) border border-(--border-default) rounded-xl p-6">
            <h3 className="font-semibold text-(--text-primary) mb-4">Quick Actions</h3>
            <div className="space-y-2">
              {[
                { label: 'Open AI Chat', icon: <MessageSquare size={18} />, path: '/app/chat', color: 'text-blue-500' },
                { label: 'View Checklist', icon: <CheckCircle2 size={18} />, path: '/app/checklist', color: 'text-green-500' },
                { label: 'Knowledge Base', icon: <Sparkles size={18} />, path: '/app/knowledge', color: 'text-purple-500' },
              ].map(action => (
                <button
                  key={action.label}
                  onClick={() => navigate(action.path)}
                  className="w-full flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-(--bg-secondary) transition-colors text-left group"
                >
                  <span className={action.color}>{action.icon}</span>
                  <span className="text-sm font-medium text-(--text-primary) group-hover:text-primary-500 transition-colors">{action.label}</span>
                  <ArrowRight size={14} className="ml-auto text-(--text-tertiary) group-hover:text-primary-500 transition-colors" />
                </button>
              ))}
            </div>
          </div>

          {/* Onboarding Phase */}
          <div className="bg-(--bg-card) border border-(--border-default) rounded-xl p-6">
            <h3 className="font-semibold text-(--text-primary) mb-4">Current Phase</h3>
            <div className="space-y-3">
              {PHASES.map(({ label: phase }, i) => {
                const isDone = i < currentPhase || (isAuthoritativelyComplete && i === currentPhase);
                const isActive = i === currentPhase && !isDone;
                return (
                  <div key={phase} className="flex items-center gap-3" aria-current={isActive ? 'step' : undefined}>
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border-2 ${
                      isActive ? 'border-primary-500 bg-primary-500/10 text-primary-500' :
                      isDone ? 'border-green-500 bg-green-500/10 text-green-500' :
                      'border-(--border-default) text-(--text-tertiary)'
                    }`}>
                      {isDone ? '✓' : i + 1}
                    </div>
                    <span className={`text-sm ${isActive ? 'text-primary-500 font-semibold' : isDone ? 'text-(--text-tertiary)' : 'text-(--text-secondary)'}`}>
                      {phase}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
