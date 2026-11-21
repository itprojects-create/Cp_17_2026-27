import React, { useCallback, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';
import {
  Activity, AlertTriangle, ArrowLeft, CheckCircle2, CircleDashed, Clock, FileCheck2,
  Mail, RefreshCw, Ticket, User as UserIcon,
} from 'lucide-react';
import { api } from '../services/api';
import { getErrorDetail } from '../services/errors';
import { useLiveRefresh } from '../hooks/useLiveRefresh';
import type { EmployeeChecklistItem, EmployeeDetail } from '../types';

const STATUS_STYLES: Record<string, string> = {
  Completed: 'bg-green-500/10 text-green-600 dark:text-green-400 border-green-500/20',
  'In Progress': 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20',
  Blocked: 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20',
  Skipped: 'bg-gray-500/10 text-(--text-secondary) border-(--border-default)',
};
const statusStyle = (status: string | null) =>
  STATUS_STYLES[status ?? ''] ?? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20';

const ACCOUNT_LABELS: Record<EmployeeDetail['employee']['account_status'], { label: string; style: string }> = {
  active: { label: 'Active account', style: 'bg-green-500/10 text-green-600 dark:text-green-400 border-green-500/20' },
  invite_pending: { label: 'Invite not accepted', style: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20' },
  unknown: { label: 'No linked account', style: 'bg-gray-500/10 text-(--text-secondary) border-(--border-default)' },
};

const formatDate = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString(undefined, { dateStyle: 'medium' }) : '—');
const relative = (iso: string | null) => (iso ? formatDistanceToNow(new Date(iso), { addSuffix: true }) : 'No activity yet');
const humanize = (value: string | null) => (value ? value.replace(/_/g, ' ') : '—');

const Badge: React.FC<{ className: string; children: React.ReactNode }> = ({ className, children }) => (
  <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border whitespace-nowrap ${className}`}>{children}</span>
);

const Card: React.FC<{ title: string; icon: React.ReactNode; children: React.ReactNode; className?: string }> = ({ title, icon, children, className = '' }) => (
  <section className={`bg-(--bg-card) border border-(--border-default) rounded-xl ${className}`}>
    <h2 className="flex items-center gap-2 px-5 py-4 border-b border-(--border-default) text-sm font-semibold text-(--text-primary)">
      {icon}{title}
    </h2>
    {children}
  </section>
);

const ChecklistRow: React.FC<{ item: EmployeeChecklistItem }> = ({ item }) => (
  <li className="px-5 py-4">
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div className="min-w-0">
        <p className="text-sm font-medium text-(--text-primary)">
          <span className="text-(--text-tertiary) font-mono text-xs mr-2">{item.id}</span>{item.title}
        </p>
        {item.description && <p className="text-xs text-(--text-secondary) mt-1">{item.description}</p>}
        <p className="text-xs text-(--text-tertiary) mt-1">{item.category} · Due {item.deadline}</p>
      </div>
      <Badge className={statusStyle(item.status)}>{item.status}</Badge>
    </div>
    {item.completion_evidence ? (
      <div className="mt-3 p-3 rounded-lg bg-(--bg-secondary) border border-(--border-default)">
        <p className="flex items-center gap-1.5 text-xs font-medium text-(--text-secondary) mb-1">
          <FileCheck2 size={13} /> Evidence
          {item.completion_source && <span className="text-(--text-tertiary) font-normal">· via {humanize(item.completion_source)}</span>}
          {item.completed_at && <span className="text-(--text-tertiary) font-normal">· {formatDate(item.completed_at)}</span>}
        </p>
        <p className="text-sm text-(--text-primary) whitespace-pre-wrap break-words">{item.completion_evidence}</p>
      </div>
    ) : item.status === 'Completed' ? (
      <p className="mt-2 flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-400">
        <AlertTriangle size={13} /> Marked complete without evidence, so it doesn't count toward progress
      </p>
    ) : null}
  </li>
);

export const EmployeeDetailPage: React.FC = () => {
  const { sessionId = '' } = useParams();
  const [detail, setDetail] = useState<EmployeeDetail | null>(null);
  const [error, setError] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const load = useCallback(async (showSpinner = false) => {
    if (showSpinner) setIsRefreshing(true);
    try {
      setDetail(await api.getEmployeeDetail(sessionId));
      setError('');
    } catch (e) {
      setError(getErrorDetail(e, 'Could not load this onboarding.'));
    } finally {
      setIsRefreshing(false);
    }
  }, [sessionId]);

  // Quiet background refresh while HR watches; the button shows a spinner for manual refreshes.
  const refreshQuietly = useCallback(() => load(), [load]);
  useLiveRefresh(refreshQuietly, 15000);

  const backLink = (
    <Link to="/app/admin" className="inline-flex items-center gap-1.5 text-sm text-primary-500 hover:text-primary-400 mb-4">
      <ArrowLeft size={16} /> HR Dashboard
    </Link>
  );

  if (error && !detail) {
    return (
      <div className="px-4 py-5 sm:p-6 md:p-8 max-w-6xl mx-auto">
        {backLink}
        <div className="bg-(--bg-card) border border-(--border-default) rounded-xl p-10 text-center">
          <AlertTriangle size={36} className="mx-auto mb-3 text-amber-500" />
          <p className="font-medium text-(--text-primary)">{error}</p>
        </div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="px-4 py-5 sm:p-6 md:p-8 max-w-6xl mx-auto space-y-4">
        <div className="skeleton h-32" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">{[1, 2, 3, 4].map(i => <div key={i} className="skeleton h-24" />)}</div>
        <div className="skeleton h-96" />
      </div>
    );
  }

  const { employee, session, progress, checklist, starter_ticket: ticket, activity } = detail;
  const account = ACCOUNT_LABELS[employee.account_status];
  const stats = [
    { label: 'Verified complete', value: `${progress.completed}/${progress.total}`, icon: <CheckCircle2 size={18} className="text-green-500" /> },
    { label: 'Remaining', value: progress.pending, icon: <CircleDashed size={18} className="text-amber-500" /> },
    { label: 'Blocked', value: progress.blocked, icon: <AlertTriangle size={18} className="text-red-500" /> },
    { label: 'Last activity', value: relative(session.last_activity_at), icon: <Clock size={18} className="text-primary-500" /> },
  ];

  return (
    <div className="px-4 py-5 sm:p-6 md:p-8 max-w-6xl mx-auto animate-fade-in">
      {backLink}

      <div className="bg-(--bg-card) border border-(--border-default) rounded-xl p-5 sm:p-6 mb-6">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div className="flex items-start gap-4 min-w-0">
            <div className="w-12 h-12 shrink-0 rounded-full bg-primary-500/10 text-primary-500 flex items-center justify-center text-lg font-bold">
              {(employee.name || employee.email || '?').charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0">
              <h1 className="text-xl font-bold text-(--text-primary) truncate">{employee.name || employee.username || 'Unknown employee'}</h1>
              <p className="flex items-center gap-1.5 text-sm text-(--text-secondary) truncate"><Mail size={14} className="shrink-0" />{employee.email || '—'}</p>
              <div className="flex flex-wrap gap-2 mt-3">
                <Badge className={statusStyle(session.status === 'Completed' ? 'Completed' : 'In Progress')}>{session.status || 'In Progress'}</Badge>
                <Badge className="bg-(--bg-secondary) text-(--text-secondary) border-(--border-default) capitalize">Phase: {humanize(session.current_phase)}</Badge>
                <Badge className={account.style}>{account.label}</Badge>
              </div>
            </div>
          </div>
          <button
            onClick={() => load(true)}
            disabled={isRefreshing}
            className="self-start flex items-center gap-2 px-3.5 py-2 rounded-lg border border-(--border-default) text-(--text-primary) text-sm font-medium hover:bg-(--bg-secondary) transition-colors"
          >
            <RefreshCw size={15} className={isRefreshing ? 'animate-spin text-primary-500' : ''} /> Refresh
          </button>
        </div>

        <div className="mt-6">
          <div className="flex justify-between text-sm mb-1.5">
            <span className="font-medium text-(--text-primary)">Onboarding progress</span>
            <span className="font-semibold text-(--text-primary)">{Math.round(progress.percentage)}%</span>
          </div>
          <div
            className="h-2.5 rounded-full bg-(--bg-tertiary) overflow-hidden"
            role="progressbar" aria-valuenow={Math.round(progress.percentage)} aria-valuemin={0} aria-valuemax={100}
          >
            <div className="h-full rounded-full bg-primary-500 transition-all" style={{ width: `${progress.percentage}%` }} />
          </div>
          <p className="text-xs text-(--text-tertiary) mt-1.5">
            Started {formatDate(session.started_at)}
            {session.completed_at && <> · Completed {formatDate(session.completed_at)}</>}
            {progress.pending_verification > 0 && <> · {progress.pending_verification} awaiting verification</>}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-6">
        {stats.map(s => (
          <div key={s.label} className="bg-(--bg-card) border border-(--border-default) rounded-xl p-4">
            <div className="flex items-center gap-2 text-xs text-(--text-secondary) mb-1">{s.icon}{s.label}</div>
            <p className="text-lg font-bold text-(--text-primary) truncate">{s.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card title={`Checklist (${checklist.length})`} icon={<FileCheck2 size={16} className="text-primary-500" />} className="lg:col-span-2">
          {checklist.length ? (
            <ul className="divide-y divide-(--border-default)">
              {checklist.map(item => <ChecklistRow key={item.id} item={item} />)}
            </ul>
          ) : (
            <p className="px-5 py-10 text-center text-sm text-(--text-secondary)">
              No plan yet. It's generated when the employee completes their profile.
            </p>
          )}
        </Card>

        <div className="space-y-6">
          <Card title="Starter ticket" icon={<Ticket size={16} className="text-purple-500" />}>
            <div className="px-5 py-4">
              {ticket?.reference ? (
                <>
                  <p className="font-mono text-sm font-semibold text-(--text-primary) break-all">{ticket.reference}</p>
                  <p className="text-xs text-(--text-tertiary) mt-1">Assigned {formatDate(ticket.assigned_at)}</p>
                </>
              ) : (
                <p className="text-sm text-(--text-secondary)">Not assigned yet. It's assigned when the employee reaches their first task.</p>
              )}
            </div>
          </Card>

          <Card title="Profile" icon={<UserIcon size={16} className="text-primary-500" />}>
            <dl className="px-5 py-4 space-y-3 text-sm">
              {[
                ['Role', employee.role],
                ['Experience', employee.years_of_experience != null ? `${employee.years_of_experience} years` : null],
                ['Persona match', session.persona_match],
                ['Joined', formatDate(employee.joined_at)],
                ['Invited by', employee.invited_by],
              ].map(([label, value]) => (
                <div key={label} className="flex justify-between gap-4">
                  <dt className="text-(--text-secondary)">{label}</dt>
                  <dd className="text-(--text-primary) text-right">{value || '—'}</dd>
                </div>
              ))}
              {[...employee.programming_languages, ...employee.tech_stack].length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {[...new Set([...employee.programming_languages, ...employee.tech_stack])].map(t => (
                    <span key={t} className="text-xs px-2 py-0.5 rounded-full bg-(--bg-tertiary) text-(--text-secondary)">{t}</span>
                  ))}
                </div>
              )}
            </dl>
          </Card>

          <Card title="Activity" icon={<Activity size={16} className="text-primary-500" />}>
            {activity.length ? (
              <ol className="px-5 py-4 space-y-4 max-h-96 overflow-y-auto">
                {activity.map(event => (
                  <li key={event.id} className="relative pl-4 border-l-2 border-(--border-default)">
                    <p className="text-sm font-medium text-(--text-primary)">{event.label}</p>
                    {event.details && <p className="text-xs text-(--text-secondary) mt-0.5 break-words">{event.details}</p>}
                    {event.timestamp && <p className="text-[11px] text-(--text-tertiary) mt-0.5">{relative(event.timestamp)}</p>}
                  </li>
                ))}
              </ol>
            ) : (
              <p className="px-5 py-6 text-sm text-(--text-secondary)">No activity recorded yet.</p>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
};
