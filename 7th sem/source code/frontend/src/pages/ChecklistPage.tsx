import React, { useEffect, useState } from 'react';
import {
  CheckCircle2, Circle, Clock, AlertTriangle, ChevronDown, ChevronUp,
  Filter, Search
} from 'lucide-react';
import { api } from '../services/api';
import type { ChecklistItemType, ProgressData } from '../types';
import toast from 'react-hot-toast';

const statusConfig: Record<string, { color: string; bg: string; icon: React.ReactNode }> = {
  'Not Started': { color: 'text-surface-400', bg: 'bg-surface-400/10', icon: <Circle size={16} /> },
  'In Progress': { color: 'text-blue-500', bg: 'bg-blue-500/10', icon: <Clock size={16} /> },
  'Completed': { color: 'text-green-500', bg: 'bg-green-500/10', icon: <CheckCircle2 size={16} /> },
  'Blocked': { color: 'text-red-500', bg: 'bg-red-500/10', icon: <AlertTriangle size={16} /> },
};

export const ChecklistPage: React.FC = () => {
  const [checklist, setChecklist] = useState<ChecklistItemType[]>([]);
  const [progress, setProgress] = useState<ProgressData | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filter, setFilter] = useState('All');
  const [search, setSearch] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [sessionId, setSessionId] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const sessions = await api.getSessions();
        if (sessions.length > 0) {
          const sid = sessions[0].session_id;
          setSessionId(sid);
          const items = await api.getChecklist(sid);
          setChecklist(items);
          const prog = await api.getProgress(sid);
          setProgress(prog);
        }
      } catch (e) { console.error(e); }
      finally { setIsLoading(false); }
    };
    load();
  }, []);

  const handleUpdateStatus = async (itemId: string, newStatus: string) => {
    if (!sessionId) return;
    try {
      await api.updateChecklistItem(
        sessionId,
        itemId,
        newStatus,
        newStatus === 'Completed' ? 'User confirmed completion from the onboarding checklist.' : undefined,
      );
      toast.success(`Task marked as ${newStatus}`);
      const items = await api.getChecklist(sessionId);
      setChecklist(items);
      const prog = await api.getProgress(sessionId);
      setProgress(prog);
    } catch (e) { console.error(e); }
  };

  const filtered = checklist.filter(item => {
    if (filter !== 'All' && item.status !== filter) return false;
    if (search && !item.task.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const categories = [...new Set(checklist.map(c => c.category))];
  const pct = progress?.percentage ?? 0;

  if (isLoading) {
    return (
      <div className="p-4 sm:p-8 space-y-4">
        <div className="skeleton h-20 w-full" />
        {[1,2,3,4,5].map(i => <div key={i} className="skeleton h-16" />)}
      </div>
    );
  }

  return (
    <div className="px-4 py-5 sm:p-6 md:p-8 max-w-5xl mx-auto animate-fade-in">
      {/* Header with Progress */}
      <div className="bg-(--bg-card) border border-(--border-default) rounded-xl p-6 mb-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-(--text-primary)">Onboarding Checklist</h1>
            <p className="text-(--text-secondary) mt-1">
              {progress?.completed ?? 0} of {progress?.total ?? 0} tasks completed
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-3xl font-bold text-primary-500">{pct}%</span>
          </div>
        </div>
        <div className="mt-4 h-3 bg-(--bg-tertiary) rounded-full overflow-hidden">
          <div className="h-full bg-linear-to-r from-primary-500 to-accent-500 rounded-full transition-all duration-700"
            style={{ width: `${pct}%` }} />
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-(--text-tertiary)" />
          <input type="text" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search tasks..."
            className="w-full pl-9 pr-4 py-2 rounded-lg border border-(--border-default) bg-(--bg-secondary) text-sm text-(--text-primary) focus:outline-none focus:ring-2 focus:ring-primary-500" />
        </div>
        <div className="relative">
          <Filter size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-(--text-tertiary)" />
          <select value={filter} onChange={e => setFilter(e.target.value)}
            className="pl-9 pr-8 py-2 rounded-lg border border-(--border-default) bg-(--bg-secondary) text-sm text-(--text-primary) focus:outline-none focus:ring-2 focus:ring-primary-500 appearance-none">
            <option value="All">All Status</option>
            <option value="Not Started">Not Started</option>
            <option value="In Progress">In Progress</option>
            <option value="Completed">Completed</option>
            <option value="Blocked">Blocked</option>
          </select>
        </div>
      </div>

      {/* Checklists by Category */}
      {categories.map(cat => {
        const catItems = filtered.filter(i => i.category === cat);
        if (catItems.length === 0) return null;
        return (
          <div key={cat} className="mb-6">
            <h3 className="text-sm font-semibold text-(--text-tertiary) uppercase tracking-wider mb-3 px-1">{cat}</h3>
            <div className="space-y-2">
              {catItems.map(item => {
                const cfg = statusConfig[item.status] || statusConfig['Not Started'];
                const isExpanded = expandedId === item.id;
                return (
                  <div key={item.id}
                    className="bg-(--bg-card) border border-(--border-default) rounded-xl overflow-hidden hover:shadow-sm transition-all">
                    <div className="flex items-center gap-3 p-4 cursor-pointer" onClick={() => setExpandedId(isExpanded ? null : item.id)}>
                      <div className={cfg.color}>{cfg.icon}</div>
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm font-medium ${item.status === 'Completed' ? 'line-through text-(--text-tertiary)' : 'text-(--text-primary)'}`}>
                          {item.task}
                        </p>
                      </div>
                      <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${cfg.color} ${cfg.bg}`}>{item.status}</span>
                      {isExpanded ? <ChevronUp size={16} className="text-(--text-tertiary)" /> : <ChevronDown size={16} className="text-(--text-tertiary)" />}
                    </div>
                    {isExpanded && (
                      <div className="px-4 pb-4 pt-0 border-t border-(--border-default) animate-fade-in">
                        <div className="grid grid-cols-2 gap-4 mt-3 text-sm">
                          <div>
                            <span className="text-(--text-tertiary)">Owner:</span>
                            <span className="ml-2 text-(--text-primary)">{item.owner}</span>
                          </div>
                          <div>
                            <span className="text-(--text-tertiary)">Deadline:</span>
                            <span className="ml-2 text-(--text-primary)">{item.deadline || 'No deadline'}</span>
                          </div>
                        </div>
                        <div className="mt-4 flex gap-2 flex-wrap">
                          {item.status !== 'Completed' && (
                            <button onClick={() => handleUpdateStatus(item.id, 'Completed')}
                              className="px-3 py-1.5 rounded-lg bg-green-500/10 text-green-500 text-sm font-medium hover:bg-green-500/20 transition-colors">
                              Mark Complete
                            </button>
                          )}
                          {item.status === 'Not Started' && (
                            <button onClick={() => handleUpdateStatus(item.id, 'In Progress')}
                              className="px-3 py-1.5 rounded-lg bg-blue-500/10 text-blue-500 text-sm font-medium hover:bg-blue-500/20 transition-colors">
                              Start Task
                            </button>
                          )}
                          {item.status !== 'Blocked' && item.status !== 'Completed' && (
                            <button onClick={() => handleUpdateStatus(item.id, 'Blocked')}
                              className="px-3 py-1.5 rounded-lg bg-red-500/10 text-red-500 text-sm font-medium hover:bg-red-500/20 transition-colors">
                              Mark Blocked
                            </button>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}

      {filtered.length === 0 && (
        <div className="text-center py-16">
          <CheckCircle2 size={48} className="text-(--text-tertiary) mx-auto mb-3" />
          <p className="text-(--text-primary) font-medium">No tasks found</p>
          <p className="text-sm text-(--text-secondary)">Try adjusting your filters</p>
        </div>
      )}
    </div>
  );
};
