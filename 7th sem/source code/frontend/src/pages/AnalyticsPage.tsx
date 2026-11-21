import React, { useMemo, useState } from 'react';
import {
  BarChart3, Clock, Users, AlertTriangle,
  CheckCircle2, RefreshCw
} from 'lucide-react';
import { api } from '../services/api';
import { useLiveRefresh } from '../hooks/useLiveRefresh';

interface AnalyticsData {
  averageOnboardingTime: number | null;
  medianOnboardingTime: number | null;
  totalSessions: number;
  completedOnboardings: number;
  completionRate: number;
  activeOnboardings: number;
  blockedTasks: number;
  pendingVerificationTasks: number;
  weeklyCompletions: Array<{ week: string; completions: number }>;
  departmentBreakdown: Array<{ name: string; count: number; color?: string }>;
  insights: Array<{ label: string; value: string; trend: string | null }>;
  phaseBreakdown: Array<{ phase: string; count: number; pct: number }>;
}

export const AnalyticsPage: React.FC = () => {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const loadData = async (refresh = false) => {
    if (refresh) setIsRefreshing(true);
    try {
      const data = await api.getAnalytics();
      setAnalytics(data);
    } catch (e) {
      console.error('Failed to load analytics:', e);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  // Analytics aggregate every employee's progress; refresh while HR has the page open.
  useLiveRefresh(loadData, 30000);

  const weeklyData = useMemo(() => {
    if (!analytics?.weeklyCompletions || !analytics.weeklyCompletions.length) {
      return [
        { label: 'W1', value: 0 },
        { label: 'W2', value: 0 },
        { label: 'W3', value: 0 },
        { label: 'W4', value: 0 },
        { label: 'W5', value: 0 },
      ];
    }
    return analytics.weeklyCompletions.map((item, idx) => {
      return {
        label: item.week.replace('Week ', 'W') || `W${idx + 1}`,
        value: item.completions,
      };
    });
  }, [analytics]);

  const maxVal = useMemo(() => {
    const vals = weeklyData.map(d => d.value);
    const max = Math.max(...vals, 0);
    return max > 0 ? max : 5;
  }, [weeklyData]);

  const departmentData = useMemo(() => {
    if (!analytics?.departmentBreakdown) return [];
    const palette = ['bg-blue-500', 'bg-purple-500', 'bg-emerald-500', 'bg-amber-500', 'bg-cyan-500', 'bg-indigo-500'];

    return analytics.departmentBreakdown.map((item, i) => ({
      name: item.name,
      value: item.count,
      color: palette[i % palette.length],
    }));
  }, [analytics]);

  const deptMax = useMemo(() => {
    const vals = departmentData.map(d => d.value);
    const max = Math.max(...vals, 0);
    return max > 0 ? max : 1;
  }, [departmentData]);

  if (isLoading || !analytics) {
    return (
      <div className="p-4 sm:p-8 space-y-6">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">{[1, 2, 3, 4].map(i => <div key={i} className="skeleton h-28" />)}</div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6"><div className="skeleton h-64" /><div className="skeleton h-64" /></div>
      </div>
    );
  }

  return (
    <div className="px-4 py-5 sm:p-6 md:p-8 max-w-7xl mx-auto animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 sm:mb-8">
        <div>
          <h1 className="text-2xl font-bold text-(--text-primary) flex items-center gap-2">
            <BarChart3 size={24} className="text-primary-500" /> HR & Engineering Analytics
          </h1>
          <p className="text-(--text-secondary) mt-1">Onboarding metrics, team distribution, and velocity insights</p>
        </div>
        <button
          onClick={() => loadData(true)}
          disabled={isRefreshing}
          className="flex items-center gap-2 px-3.5 py-2 rounded-lg border border-(--border-default) bg-(--bg-card) text-(--text-primary) text-sm font-medium hover:bg-(--bg-secondary) transition-colors"
        >
          <RefreshCw size={15} className={isRefreshing ? 'animate-spin text-primary-500' : ''} />
          <span>{isRefreshing ? 'Refreshing...' : 'Refresh'}</span>
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-8">
        {[
          { label: 'Avg. Onboarding Time', value: analytics.averageOnboardingTime == null ? 'No data' : `${analytics.averageOnboardingTime} days`, change: null, up: false, icon: <Clock size={20} />, color: 'from-blue-500 to-blue-600' },
          { label: 'Completion Rate', value: `${Math.round(analytics.completionRate || 0)}%`, change: null, up: true, icon: <CheckCircle2 size={20} />, color: 'from-green-500 to-emerald-600' },
          { label: 'Active Onboardings', value: String(analytics.activeOnboardings ?? 0), change: null, up: true, icon: <Users size={20} />, color: 'from-purple-500 to-purple-600' },
          { label: 'Blocked Tasks', value: String(analytics.blockedTasks ?? 0), change: null, up: false, icon: <AlertTriangle size={20} />, color: 'from-red-500 to-red-600' },
        ].map(kpi => (
          <div key={kpi.label} className="bg-(--bg-card) border border-(--border-default) rounded-xl p-4 sm:p-5 shadow-xs min-w-0">
            <div className="flex items-center justify-between mb-3">
              <div className={`p-2.5 rounded-lg bg-linear-to-br ${kpi.color} text-white`}>{kpi.icon}</div>
              {kpi.change && <span className="text-xs text-(--text-tertiary)">No comparison data</span>}
            </div>
            <p className="text-xl sm:text-2xl font-bold text-(--text-primary) truncate">{kpi.value}</p>
            <p className="text-xs sm:text-sm text-(--text-secondary) mt-0.5">{kpi.label}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Weekly Completions Chart */}
        <div className="bg-(--bg-card) border border-(--border-default) rounded-xl p-6 shadow-xs">
          <div className="flex items-center justify-between mb-6">
            <h3 className="font-semibold text-(--text-primary)">Weekly Completions</h3>
            <span className="text-xs text-(--text-tertiary)">Last 5 weeks</span>
          </div>
          <div className="flex items-end gap-3 h-48 pt-4">
            {weeklyData.map((item, i) => (
              <div key={i} className="flex-1 flex flex-col items-center gap-2 h-full justify-end">
                <span className="text-xs font-semibold text-(--text-secondary)">{item.value}</span>
                <div className="w-full bg-(--bg-tertiary) rounded-t-lg overflow-hidden flex items-end" style={{ height: '120px' }}>
                  <div
                    className="w-full bg-linear-to-t from-primary-600 to-primary-400 rounded-t-lg transition-all duration-700"
                    style={{ height: `${maxVal ? Math.max((item.value / maxVal) * 100, 8) : 8}%` }}
                  />
                </div>
                <span className="text-[10px] font-medium text-(--text-tertiary)">{item.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Department Breakdown */}
        <div className="bg-(--bg-card) border border-(--border-default) rounded-xl p-6 shadow-xs">
          <div className="flex items-center justify-between mb-6">
            <h3 className="font-semibold text-(--text-primary)">Persona & Role Distribution</h3>
            <span className="text-xs text-(--text-tertiary)">By active engineers</span>
          </div>
          <div className="space-y-4">
            {departmentData.map(dept => (
              <div key={dept.name}>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-sm font-medium text-(--text-primary)">{dept.name}</span>
                  <span className="text-sm text-(--text-secondary)">{dept.value} developer{dept.value === 1 ? '' : 's'}</span>
                </div>
                <div className="h-2.5 bg-(--bg-tertiary) rounded-full overflow-hidden">
                  <div
                    className={`h-full ${dept.color} rounded-full transition-all duration-700`}
                    style={{ width: `${deptMax ? (dept.value / deptMax) * 100 : 0}%` }}
                  />
                </div>
              </div>
            ))}
            {departmentData.length === 0 && (
              <p className="text-sm text-(--text-tertiary) text-center py-8">No department data recorded yet</p>
            )}
          </div>
        </div>

        {/* Productivity Insights */}
        <div className="bg-(--bg-card) border border-(--border-default) rounded-xl p-6 shadow-xs">
          <h3 className="font-semibold text-(--text-primary) mb-4">Productivity & Onboarding Insights</h3>
          <div className="space-y-3">
            {(analytics.insights || []).map(insight => (
              <div key={insight.label} className="flex items-center justify-between p-3 rounded-lg bg-(--bg-secondary)/50 border border-(--border-subtle) hover:bg-(--bg-secondary) transition-colors">
                <span className="text-sm text-(--text-secondary)">{insight.label}</span>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-bold text-(--text-primary)">{insight.value}</span>
                  <span className="text-xs text-green-500 font-medium">{insight.trend}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Onboarding Timeline Stats */}
        <div className="bg-(--bg-card) border border-(--border-default) rounded-xl p-6 shadow-xs">
          <h3 className="font-semibold text-(--text-primary) mb-4">Onboarding Phases Breakdown</h3>
          <div className="space-y-3">
            {(analytics.phaseBreakdown || []).map(p => (
              <div key={p.phase} className="flex items-center gap-4">
                <span className="text-sm text-(--text-secondary) w-40 shrink-0">{p.phase}</span>
                <div className="flex-1 h-2 bg-(--bg-tertiary) rounded-full overflow-hidden">
                  <div className="h-full bg-linear-to-r from-primary-500 to-accent-500 rounded-full" style={{ width: `${p.pct}%` }} />
                </div>
                <span className="text-xs text-(--text-tertiary) w-16 text-right">{p.count} sessions</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
