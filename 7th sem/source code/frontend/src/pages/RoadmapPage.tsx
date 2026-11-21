import React, { useEffect, useMemo, useState } from 'react';
import { Map, CheckCircle2, Circle, Lock, ArrowRight, Sparkles } from 'lucide-react';
import { api } from '../services/api';

interface RoadmapStep {
  id: string;
  title: string;
  description: string;
  tasks: string[];
  status: 'completed' | 'active' | 'locked';
  duration: string;
}

export const RoadmapPage: React.FC = () => {
  const [roadmapSteps, setRoadmapSteps] = useState<RoadmapStep[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [progress, setProgress] = useState<{ percentage: number; completed: number; total: number } | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await api.getRoadmap();
        setRoadmapSteps(data.steps);
        setProgress(data.progress ?? null);
        const active = data.steps.find((s) => s.status === 'active');
        setExpandedId(active?.id || data.steps[0]?.id || null);
      } catch (e) {
        console.error(e);
      }
    };
    load();
  }, []);

  const completedSteps = useMemo(() => roadmapSteps.filter(s => s.status === 'completed').length, [roadmapSteps]);
  const pct = progress?.percentage ?? (roadmapSteps.length ? Math.round((completedSteps / roadmapSteps.length) * 100) : 0);

  if (!roadmapSteps.length) {
    return <div className="p-8"><div className="skeleton h-56 w-full" /></div>;
  }

  return (
    <div className="px-4 py-5 sm:p-6 md:p-8 max-w-4xl mx-auto animate-fade-in">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-(--text-primary) flex items-center gap-2">
          <Map size={24} className="text-primary-500" /> Onboarding Roadmap
        </h1>
        <p className="text-(--text-secondary) mt-1">Your interactive guide to getting productive</p>
      </div>

      {/* Progress Overview */}
      <div className="bg-linear-to-r from-primary-600 to-accent-500 rounded-2xl p-6 mb-8 text-white relative overflow-hidden">
        <div className="absolute top-0 right-0 w-48 h-48 bg-white/5 rounded-full -translate-y-1/2 translate-x-1/4" />
        <div className="relative z-10 flex items-center justify-between">
          <div>
            <p className="text-white/80 text-sm">Your Progress</p>
            <p className="text-3xl font-bold mt-1">{Number.isFinite(pct) ? pct : 0}% Complete</p>
            <p className="text-white/70 text-sm mt-1">
              {progress ? `${progress.completed} of ${progress.total} qualifying tasks complete` : `Step ${completedSteps + 1} of ${roadmapSteps.length}`}
            </p>
          </div>
          <div className="hidden sm:block">
            <Sparkles size={48} className="text-white/20" />
          </div>
        </div>
        <div className="mt-4 h-2 bg-white/20 rounded-full overflow-hidden">
          <div className="h-full bg-white rounded-full transition-all duration-700" style={{ width: `${pct}%` }} />
        </div>
      </div>

      {/* Roadmap Steps */}
      <div className="relative">
        {/* Connector Line */}
        <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-(--border-default)" />

        <div className="space-y-4">
          {roadmapSteps.map((step, i) => {
            const isExpanded = expandedId === step.id;
            return (
              <div key={step.id} className="relative flex gap-5 animate-fade-in" style={{ animationDelay: `${i * 60}ms` }}>
                {/* Step Indicator */}
                <div className={`relative z-10 w-12 h-12 rounded-full flex items-center justify-center shrink-0 border-2 transition-all ${
                  step.status === 'completed'
                    ? 'bg-green-500 border-green-500 text-white shadow-lg shadow-green-500/20'
                    : step.status === 'active'
                    ? 'bg-primary-500 border-primary-500 text-white shadow-lg shadow-primary-500/30 animate-pulse-glow'
                    : 'bg-(--bg-card) border-(--border-default) text-(--text-tertiary)'
                }`}>
                  {step.status === 'completed' ? <CheckCircle2 size={20} /> :
                   step.status === 'active' ? <span className="text-sm font-bold">{i + 1}</span> :
                   <Lock size={16} />}
                </div>

                {/* Content Card */}
                <div
                  onClick={() => setExpandedId(isExpanded ? null : step.id)}
                  className={`flex-1 bg-(--bg-card) border rounded-xl overflow-hidden cursor-pointer transition-all hover:shadow-sm ${
                    step.status === 'active'
                      ? 'border-primary-500/30 shadow-sm'
                      : step.status === 'completed'
                      ? 'border-green-500/10'
                      : 'border-(--border-default) opacity-60'
                  }`}
                >
                  <div className="p-5">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className={`font-semibold ${
                            step.status === 'active' ? 'text-primary-500' :
                            step.status === 'completed' ? 'text-(--text-primary)' : 'text-(--text-tertiary)'
                          }`}>{step.title}</h3>
                          {step.status === 'active' && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary-500/10 text-primary-500 font-bold uppercase">Current</span>
                          )}
                        </div>
                        <p className="text-xs text-(--text-tertiary) mt-0.5">{step.duration}</p>
                      </div>
                    </div>
                    <p className="text-sm text-(--text-secondary) mt-2">{step.description}</p>

                    {isExpanded && (
                      <div className="mt-4 pt-4 border-t border-(--border-default) animate-fade-in">
                        <p className="text-xs font-semibold text-(--text-tertiary) uppercase tracking-wider mb-3">Tasks</p>
                        <div className="space-y-2">
                          {step.tasks.map((task, ti) => (
                            <div key={ti} className="flex items-center gap-2.5">
                              {step.status === 'completed' ? (
                                <CheckCircle2 size={16} className="text-green-500 shrink-0" />
                              ) : (
                                <Circle size={16} className="text-(--text-tertiary) shrink-0" />
                              )}
                              <span className={`text-sm ${step.status === 'completed' ? 'text-(--text-tertiary) line-through' : 'text-(--text-primary)'}`}>
                                {task}
                              </span>
                            </div>
                          ))}
                        </div>
                        {step.status === 'active' && (
                          <button className="mt-4 flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors">
                            Continue <ArrowRight size={14} />
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
