import React, { useEffect, useMemo, useState } from 'react';
import {
  UserPlus, Settings, GitCommit, CheckCircle2, MessageSquare,
  Code, BookOpen, Zap, Flag, Ticket, Mail
} from 'lucide-react';
import { api } from '../services/api';

interface TimelineEvent {
  id: string;
  title: string;
  description: string;
  date: string;
  icon: React.ReactNode;
  color: string;
  completed: boolean;
}

const iconByKind: Record<string, React.ReactNode> = {
  account: <UserPlus size={18} />,
  profile: <Settings size={18} />,
  task: <Code size={18} />,
  chat: <MessageSquare size={18} />,
  ticket: <Ticket size={18} />,
  email: <Mail size={18} />,
  knowledge: <BookOpen size={18} />,
  commit: <GitCommit size={18} />,
  completed: <CheckCircle2 size={18} />,
};

const colorByKind: Record<string, string> = {
  account: 'bg-blue-500',
  profile: 'bg-purple-500',
  task: 'bg-green-500',
  chat: 'bg-cyan-500',
  ticket: 'bg-indigo-500',
  email: 'bg-rose-500',
  knowledge: 'bg-amber-500',
  commit: 'bg-orange-500',
  completed: 'bg-emerald-500',
};

export const TimelinePage: React.FC = () => {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState<{ percentage: number; completed: number; total: number } | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await api.getTimeline();
        const mapped: TimelineEvent[] = data.events.map((e) => ({
          id: e.id,
          title: e.title,
          description: e.description,
          date: new Date(e.date).toLocaleString(),
          icon: iconByKind[e.kind] || <Flag size={18} />,
          color: colorByKind[e.kind] || 'bg-red-500',
          completed: e.completed,
        }));
        setEvents(mapped);
        setProgress(data.progress ?? null);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const completedCount = useMemo(() => progress?.completed ?? events.filter((e) => e.completed).length, [events, progress]);
  const totalCount = progress?.total ?? events.length;
  const progressPercentage = progress?.percentage ?? (events.length ? Math.round((completedCount / events.length) * 100) : 0);

  if (loading) {
    return <div className="p-8"><div className="skeleton h-56 w-full" /></div>;
  }

  return (
    <div className="px-4 py-5 sm:p-6 md:p-8 max-w-4xl mx-auto animate-fade-in">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-(--text-primary) flex items-center gap-2">
          <Zap size={24} className="text-primary-500" /> Activity Timeline
        </h1>
        <p className="text-(--text-secondary) mt-1">Your onboarding journey, step by step</p>
      </div>

      {/* Progress Summary */}
      <div className="bg-(--bg-card) border border-(--border-default) rounded-xl p-6 mb-8">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-(--text-secondary)">Overall Progress</p>
            <p className="text-2xl font-bold text-(--text-primary)">{completedCount} / {totalCount} qualifying tasks</p>
          </div>
          <div className="text-3xl font-bold text-primary-500">{progressPercentage}%</div>
        </div>
        <div className="mt-3 h-2 bg-(--bg-tertiary) rounded-full overflow-hidden">
          <div className="h-full bg-linear-to-r from-primary-500 to-accent-500 rounded-full transition-all"
            style={{ width: `${progressPercentage}%` }} />
        </div>
      </div>

      {/* Timeline */}
      <div className="relative">
        {/* Vertical Line */}
        <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-(--border-default)" />

        <div className="space-y-1">
          {events.map((event, i) => (
            <div key={event.id} className="relative flex gap-5 animate-fade-in" style={{ animationDelay: `${i * 80}ms` }}>
              {/* Icon */}
              <div className={`relative z-10 w-12 h-12 rounded-full flex items-center justify-center shrink-0 text-white ${
                event.completed ? event.color : 'bg-(--bg-tertiary)'
              } ${event.completed ? 'shadow-lg' : ''}`}>
                {event.completed ? event.icon : <div className="w-3 h-3 rounded-full bg-(--text-tertiary)" />}
              </div>

              {/* Content */}
              <div className={`flex-1 pb-8 ${!event.completed ? 'opacity-50' : ''}`}>
                <div className="bg-(--bg-card) border border-(--border-default) rounded-xl p-5 hover:shadow-sm transition-all">
                  <div className="flex items-center justify-between mb-1">
                    <h3 className="font-semibold text-(--text-primary)">{event.title}</h3>
                    {event.completed && (
                      <CheckCircle2 size={16} className="text-green-500" />
                    )}
                  </div>
                  <p className="text-sm text-(--text-secondary)">{event.description}</p>
                  <p className="text-xs text-(--text-tertiary) mt-2">{event.date}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
