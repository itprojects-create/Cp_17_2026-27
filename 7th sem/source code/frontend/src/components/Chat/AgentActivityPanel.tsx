import React from 'react';
import { 
  UserCheck, 
  Search, 
  FileText, 
  Sparkles, 
  CheckCircle2, 
  Ticket, 
  Mail, 
  Cpu, 
  Activity, 
  Clock, 
  AlertCircle,
  Loader2,
  ChevronRight,
  Workflow
} from 'lucide-react';
import type { AgentActivityItem } from '../../types';

interface AgentActivityPanelProps {
  activities: AgentActivityItem[];
  isLoading?: boolean;
  activePhase?: string;
  onClear?: () => void;
  className?: string;
}

export const AgentActivityPanel: React.FC<AgentActivityPanelProps> = ({
  activities,
  isLoading = false,
  activePhase = 'onboarding',
  className = '',
}) => {
  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'persona_identified':
        return <UserCheck size={16} className="text-indigo-500" />;
      case 'kb_search':
        return <Search size={16} className="text-sky-500" />;
      case 'kb_retrieved':
        return <FileText size={16} className="text-cyan-500" />;
      case 'plan_generated':
        return <Sparkles size={16} className="text-amber-500" />;
      case 'checklist_update':
        return <CheckCircle2 size={16} className="text-emerald-500" />;
      case 'ticket_created':
        return <Ticket size={16} className="text-purple-500" />;
      case 'hr_report':
        return <Mail size={16} className="text-blue-500" />;
      case 'intent_classification':
        return <Cpu size={16} className="text-violet-500" />;
      default:
        return <Activity size={16} className="text-gray-500" />;
    }
  };

  const getStatusBadge = (status: AgentActivityItem['status']) => {
    switch (status) {
      case 'running':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20 animate-pulse">
            <Loader2 size={10} className="animate-spin" />
            running
          </span>
        );
      case 'completed':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 size={10} />
            completed
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20">
            <AlertCircle size={10} />
            failed
          </span>
        );
      case 'pending':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-gray-500/10 text-gray-500 border border-gray-500/20">
            <Clock size={10} />
            pending
          </span>
        );
    }
  };

  return (
    <div className={`flex flex-col h-full bg-(--bg-secondary) border-l border-(--border-default) ${className}`}>
      {/* Panel Header */}
      <div className="p-3.5 border-b border-(--border-default) flex items-center justify-between bg-(--bg-tertiary)/40">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-primary-500/10 flex items-center justify-center text-primary-500">
            <Workflow size={14} />
          </div>
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-(--text-primary)">
              Agent Activity
            </h3>
            <p className="text-[11px] text-(--text-tertiary)">
              Live LangGraph Supervisor Workflow
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          {isLoading ? (
            <span className="flex items-center gap-1 text-[11px] font-medium text-primary-500 bg-primary-500/10 px-2 py-0.5 rounded-full animate-pulse">
              <span className="w-1.5 h-1.5 rounded-full bg-primary-500 animate-ping" />
              Active
            </span>
          ) : (
            <span className="text-[11px] font-medium text-emerald-500 bg-emerald-500/10 px-2 py-0.5 rounded-full">
              Ready
            </span>
          )}
        </div>
      </div>

      {/* Workflow Stage Visualizer for Judges */}
      <div className="px-3.5 py-2.5 bg-linear-to-r from-primary-500/5 via-accent-500/5 to-transparent border-b border-(--border-default)">
        <div className="flex items-center justify-between text-[11px] text-(--text-secondary) font-medium">
          <span className="text-(--text-tertiary)">Workflow Phase:</span>
          <span className="capitalize font-semibold text-primary-500 px-2 py-0.5 bg-primary-500/10 rounded">
            {activePhase.replace('_', ' ')}
          </span>
        </div>
      </div>

      {/* Activities Timeline List */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-3 space-y-2.5">
        {activities.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-center p-4">
            <Activity size={24} className="text-(--text-tertiary) mb-2 opacity-50" />
            <p className="text-xs font-medium text-(--text-secondary)">No agent activities yet</p>
            <p className="text-[11px] text-(--text-tertiary) mt-1">
              Actions will appear in real time as the agent routes intents, retrieves knowledge, and updates onboarding tools.
            </p>
          </div>
        ) : (
          activities.map((act, index) => (
            <div 
              key={act.id || index}
              className="p-2.5 rounded-xl border border-(--border-default) bg-(--bg-primary) hover:border-primary-500/30 transition-all shadow-2xs animate-fade-in"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-6 h-6 rounded-lg bg-(--bg-secondary) flex items-center justify-center shrink-0 border border-(--border-default)">
                    {getActivityIcon(act.type)}
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-(--text-primary) truncate">
                      {act.label}
                    </p>
                    {act.timestamp && (
                      <p className="text-[10px] text-(--text-tertiary)">
                        {new Date(act.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </p>
                    )}
                  </div>
                </div>
                <div className="shrink-0">
                  {getStatusBadge(act.status)}
                </div>
              </div>

              {act.details && (
                <div className="mt-2 pt-1.5 border-t border-(--border-default)/50 flex items-start gap-1 text-[11px] text-(--text-secondary)">
                  <ChevronRight size={12} className="shrink-0 mt-0.5 text-primary-500 opacity-70" />
                  <span className="font-mono text-[10.5px] leading-tight break-all text-(--text-secondary)">
                    {act.details}
                  </span>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Footer / Privacy & Traceability Note */}
      <div className="p-2.5 border-t border-(--border-default) bg-(--bg-tertiary)/30 text-center">
        <p className="text-[10px] text-(--text-tertiary)">
          Autonomous LangGraph Onboarding Supervisor
        </p>
      </div>
    </div>
  );
};
