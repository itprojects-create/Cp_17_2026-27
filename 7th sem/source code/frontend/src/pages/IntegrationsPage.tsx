import React, { useEffect, useMemo, useState, useCallback } from 'react';
import {
  Github, Mail, CheckCircle2,
  XCircle, Clock, ExternalLink, RefreshCw, Plug,
  Star, GitFork, AlertCircle, GitPullRequest, BookOpen,
  Users, Loader2, LogOut, ChevronRight, Lock, Globe
} from 'lucide-react';
import { api } from '../services/api';
import toast from 'react-hot-toast';
import { getErrorDetail } from '../services/errors';
import { useIntegrationWebSocket, type WSMessage } from '../hooks/useIntegrationWebSocket';
import type { IntegrationItem } from '../types';
import { useSearchParams } from 'react-router-dom';

type IntegrationStatus = IntegrationItem['status'];

interface Integration {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  status: IntegrationStatus;
  lastSync?: string;
  color: string;
}

// Tile colors live here rather than in the API response: Tailwind only generates
// classes it finds in frontend source, so backend-provided class strings render unstyled.
const colorById: Record<string, string> = {
  github: 'bg-gray-900 dark:bg-gray-600',
  email: 'bg-blue-500',
};

const iconById: Record<string, React.ReactNode> = {
  github: <Github size={24} />,
  email: <Mail size={24} />,
};

const statusBadge: Record<IntegrationStatus, { label: string; icon: React.ReactNode; classes: string }> = {
  connected: { label: 'Connected', icon: <CheckCircle2 size={14} />, classes: 'bg-green-500/10 text-green-500' },
  disconnected: { label: 'Disconnected', icon: <XCircle size={14} />, classes: 'bg-red-500/10 text-red-500' },
  pending: { label: 'Pending', icon: <Clock size={14} />, classes: 'bg-amber-500/10 text-amber-500' },
  not_configured: { label: 'Not Configured', icon: <Plug size={14} />, classes: 'bg-gray-500/10 text-gray-500' },
  misconfigured: { label: 'Misconfigured', icon: <AlertCircle size={14} />, classes: 'bg-amber-500/10 text-amber-500' },
  unavailable: { label: 'Unavailable', icon: <XCircle size={14} />, classes: 'bg-gray-500/10 text-gray-500' },
  connection_failed: { label: 'Connection Failed', icon: <AlertCircle size={14} />, classes: 'bg-red-500/10 text-red-500' },
};

type GitHubData = Awaited<ReturnType<typeof api.getGitHubData>>;

const LANG_COLORS: Record<string, string> = {
  TypeScript: '#3178c6', JavaScript: '#f1e05a', Python: '#3572A5',
  Rust: '#dea584', Go: '#00ADD8', Java: '#b07219', CSS: '#563d7c',
  HTML: '#e34c26', 'C++': '#f34b7d', C: '#555555', Ruby: '#701516',
};

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

export const IntegrationsPage: React.FC = () => {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncingAll, setSyncingAll] = useState(false);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [searchParams] = useSearchParams();

  // GitHub data panel
  const [ghData, setGhData] = useState<GitHubData | null>(null);
  const [ghLoading, setGhLoading] = useState(false);
  const [ghTab, setGhTab] = useState<'repos' | 'issues' | 'prs'>('repos');
  const [connectingGH, setConnectingGH] = useState(false);

  const loadIntegrations = async () => {
    try {
      const data = await api.getIntegrations();
      setIntegrations(data.integrations.map((i) => ({
        ...i,
        icon: iconById[i.id] || <Plug size={24} />,
        color: colorById[i.id] || 'bg-primary-500',
      })));
    } catch (e) {
      console.error(e);
      toast.error('Failed to load integrations');
    } finally {
      setLoading(false);
    }
  };

  const loadGitHubData = async () => {
    setGhLoading(true);
    try {
      const data = await api.getGitHubData();
      setGhData(data);
    } catch {
      // Not connected yet — that's fine
    } finally {
      setGhLoading(false);
    }
  };

  const onWSMessage = useCallback((data: WSMessage) => {
    const id = data.integration_id ?? '';
    const label = id.charAt(0).toUpperCase() + id.slice(1);
    if (data.type === 'integration_status') {
      setIntegrations(prev => prev.map(i =>
        i.id === id
          ? { ...i, status: (data.status as IntegrationStatus | undefined) ?? i.status, lastSync: data.lastSync }
          : i
      ));
      if (data.status === 'connected') {
        toast.success(`${label} connected!`);
        if (id === 'github') loadGitHubData();
      }
      if (data.status === 'disconnected' && id === 'github') {
        setGhData(null);
      }
    } else if (data.type === 'sync_started') {
      setSyncingId(id || null);
    } else if (data.type === 'sync_completed') {
      setSyncingId(null);
      setIntegrations(prev => prev.map(i =>
        i.id === id ? { ...i, lastSync: data.lastSync } : i
      ));
      toast.success(`${label} sync completed`);
    } else if (data.type === 'sync_failed') {
      setSyncingId(null);
      toast.error(`Sync failed: ${data.message}`);
    }
  }, []);

  const { status: wsStatus } = useIntegrationWebSocket(onWSMessage, loadIntegrations);

  useEffect(() => {
    loadIntegrations();
  }, []);

  // Check if GitHub is already connected on load
  useEffect(() => {
    api.getGitHubStatus().then(s => {
      if (s.connected) loadGitHubData();
    }).catch(() => {});
  }, []);

  // Handle return from GitHub OAuth
  useEffect(() => {
    if (searchParams.get('github') === 'connected') {
      toast.success('GitHub connected successfully!');
      loadIntegrations();
      loadGitHubData();
    }
  }, [searchParams]);

  const connectedCount = useMemo(() => integrations.filter(i => i.status === 'connected').length, [integrations]);
  const pendingCount = useMemo(() => integrations.filter(i => i.status === 'pending').length, [integrations]);
  // Everything not connected or pending needs attention (disconnected, not configured, failed...).
  const needsSetupCount = integrations.length - connectedCount - pendingCount;

  const connectGitHubOAuth = async () => {
    setConnectingGH(true);
    try {
      const { auth_url } = await api.getGitHubOAuthUrl();
      window.location.href = auth_url;
    } catch (err) {
      toast.error(getErrorDetail(err, 'Could not start GitHub OAuth flow.'));
      setConnectingGH(false);
    }
  };

  const connectNonGitHub = async (id: string) => {
    try {
      setSyncingId(id);
      await api.connectIntegration(id);
    } catch (e) {
      console.error(e);
      setSyncingId(null);
    }
  };

  const disconnectGitHub = async () => {
    try {
      setSyncingId('github');
      await api.disconnectGitHub();
      setGhData(null);
      setIntegrations(prev => prev.map(i => i.id === 'github' ? { ...i, status: 'disconnected', lastSync: undefined } : i));
      toast.success('GitHub disconnected');
    } catch {
      toast.error('Failed to disconnect GitHub');
    } finally {
      setSyncingId(null);
    }
  };

  const syncAll = async () => {
    if (syncingAll) return;
    try {
      setSyncingAll(true);
      await api.syncIntegrations();
      toast.success('All integrations sync initiated');
    } catch (e) {
      console.error(e);
    } finally {
      setSyncingAll(false);
    }
  };

  const githubIntegration = integrations.find(i => i.id === 'github');
  const isGitHubConnected = githubIntegration?.status === 'connected';

  if (loading) {
    return <div className="p-8"><div className="skeleton h-56 w-full" /></div>;
  }

  return (
    <div className="px-4 py-5 sm:p-6 md:p-8 max-w-6xl mx-auto animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 sm:mb-8">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-(--text-primary) flex items-center gap-2">
              <Plug size={24} className="text-primary-500" /> Integrations
            </h1>
            {wsStatus === 'open' ? (
              <span className="flex h-2 w-2 rounded-full bg-green-500" title="Real-time updates active" />
            ) : wsStatus === 'polling' ? (
              <span className="flex h-2 w-2 rounded-full bg-amber-500" title="Polling fallback" />
            ) : (
              <span className="flex h-2 w-2 rounded-full bg-red-500 animate-pulse" title="Connecting..." />
            )}
          </div>
          <p className="text-(--text-secondary)">Manage your onboarding tool connections</p>
        </div>
        <button
          onClick={syncAll}
          disabled={syncingAll}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-(--border-default) text-sm font-medium text-(--text-secondary) hover:bg-(--bg-secondary) transition-colors disabled:opacity-50 whitespace-nowrap shrink-0 cursor-pointer"
        >
          <RefreshCw size={16} className={syncingAll ? 'animate-spin' : ''} />
          {syncingAll ? 'Syncing...' : 'Sync All'}
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3 sm:gap-4 mb-8">
        {[
          { label: 'Connected', value: connectedCount, color: 'text-green-500' },
          { label: 'Pending', value: pendingCount, color: 'text-amber-500' },
          { label: 'Needs Setup', value: needsSetupCount, color: needsSetupCount ? 'text-red-500' : 'text-(--text-tertiary)' },
        ].map(s => (
          <div key={s.label} className="bg-(--bg-card) border border-(--border-default) rounded-xl p-3 sm:p-5 text-center">
            <p className={`text-2xl sm:text-3xl font-bold ${s.color}`}>{s.value}</p>
            <p className="text-xs sm:text-sm text-(--text-secondary) mt-1">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Integration Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        {integrations.map((integration, i) => {
          const badge = statusBadge[integration.status];
          const isSyncing = syncingId === integration.id;
          const isGH = integration.id === 'github';

          return (
            <div key={integration.id}
              className="bg-(--bg-card) border border-(--border-default) rounded-xl p-6 hover:shadow-md transition-all animate-fade-in"
              style={{ animationDelay: `${i * 80}ms` }}
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className={`w-12 h-12 rounded-xl ${integration.color} text-white flex items-center justify-center`}>
                    {integration.icon}
                  </div>
                  <div>
                    <h3 className="font-semibold text-(--text-primary)">{integration.name}</h3>
                    <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${badge.classes}`}>
                      {badge.icon} {badge.label}
                    </span>
                  </div>
                </div>
              </div>
              <p className="text-sm text-(--text-secondary) mb-4">{integration.description}</p>
              <div className="flex items-center justify-between">
                <div className="flex flex-col">
                  {integration.lastSync && (
                    <span className="text-xs text-(--text-tertiary)">Last sync: {new Date(integration.lastSync).toLocaleString()}</span>
                  )}
                  {isSyncing && (
                    <span className="text-[10px] text-primary-500 font-medium animate-pulse mt-0.5">Syncing in progress...</span>
                  )}
                </div>

                {isGH ? (
                  <div className="flex gap-2">
                    {integration.status === 'connected' ? (
                      <button
                        onClick={disconnectGitHub}
                        disabled={isSyncing}
                        className="flex items-center gap-1.5 text-sm font-medium px-3 py-1.5 rounded-lg text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50"
                      >
                        <LogOut size={14} /> Disconnect
                      </button>
                    ) : (
                      <button
                        onClick={connectGitHubOAuth}
                        disabled={connectingGH || isSyncing}
                        className="flex items-center gap-1.5 text-sm font-medium px-3 py-1.5 rounded-lg bg-gray-900 text-white hover:bg-gray-800 border border-gray-700 transition-colors disabled:opacity-50"
                      >
                        {connectingGH ? (
                          <><Loader2 size={14} className="animate-spin" /> Redirecting...</>
                        ) : (
                          <><Github size={14} /> Connect with GitHub</>
                        )}
                      </button>
                    )}
                  </div>
                ) : (
                  <button
                    onClick={() => connectNonGitHub(integration.id)}
                    disabled={isSyncing}
                    className={`flex items-center gap-1.5 text-sm font-medium px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50 ${
                      integration.status === 'connected'
                        ? 'text-(--text-secondary) hover:bg-(--bg-secondary)'
                        : 'bg-primary-500 text-white hover:bg-primary-600'
                    }`}
                  >
                    {isSyncing ? (
                      <><RefreshCw size={14} className="animate-spin" /> Syncing</>
                    ) : integration.status === 'connected' ? (
                      <>Connected <ExternalLink size={14} /></>
                    ) : (
                      <>Connect <ExternalLink size={14} /></>
                    )}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* GitHub Real Data Panel */}
      {isGitHubConnected && (
        <div className="animate-fade-in">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-8 h-8 rounded-lg bg-gray-800 flex items-center justify-center">
              <Github size={18} className="text-white" />
            </div>
            <h2 className="text-lg font-bold text-(--text-primary)">Your GitHub Activity</h2>
            <button onClick={loadGitHubData} disabled={ghLoading}
              className="ml-auto flex items-center gap-1.5 text-xs text-(--text-secondary) hover:text-(--text-primary) transition-colors">
              <RefreshCw size={13} className={ghLoading ? 'animate-spin' : ''} />
              Refresh
            </button>
          </div>

          {ghLoading && !ghData ? (
            <div className="bg-(--bg-card) border border-(--border-default) rounded-xl p-10 flex items-center justify-center">
              <Loader2 size={24} className="animate-spin text-primary-500 mr-3" />
              <span className="text-(--text-secondary)">Loading GitHub data...</span>
            </div>
          ) : ghData ? (
            <>
              {/* GitHub User Card */}
              {ghData.user && (
                <a href={ghData.user.html_url} target="_blank" rel="noopener noreferrer"
                  className="flex items-center gap-4 bg-(--bg-card) border border-(--border-default) rounded-xl p-4 mb-4 hover:border-gray-500 transition-colors group">
                  <img src={ghData.user.avatar_url} alt={ghData.user.login}
                    className="w-12 h-12 rounded-xl" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-semibold text-(--text-primary)">{ghData.user.name || ghData.user.login}</p>
                      <span className="text-xs text-(--text-secondary)">@{ghData.user.login}</span>
                    </div>
                    {ghData.user.bio && <p className="text-sm text-(--text-secondary) truncate">{ghData.user.bio}</p>}
                  </div>
                  <div className="flex gap-4 text-sm text-(--text-secondary)">
                    <span className="flex flex-col items-center"><BookOpen size={14} className="mb-0.5" />{ghData.user.public_repos}</span>
                    <span className="flex flex-col items-center"><Users size={14} className="mb-0.5" />{ghData.user.followers}</span>
                  </div>
                  <ChevronRight size={16} className="text-(--text-tertiary) group-hover:text-(--text-primary) transition-colors" />
                </a>
              )}

              {/* Tabs */}
              <div className="flex gap-1 bg-(--bg-secondary) rounded-xl p-1 mb-4 w-fit">
                {([
                  { key: 'repos', label: 'Repositories', count: ghData.repos.length, icon: <BookOpen size={14} /> },
                  { key: 'issues', label: 'Issues', count: ghData.issues.length, icon: <AlertCircle size={14} /> },
                  { key: 'prs', label: 'Pull Requests', count: ghData.pull_requests.length, icon: <GitPullRequest size={14} /> },
                ] as const).map(tab => (
                  <button key={tab.key}
                    onClick={() => setGhTab(tab.key)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                      ghTab === tab.key
                        ? 'bg-(--bg-card) text-(--text-primary) shadow-sm'
                        : 'text-(--text-secondary) hover:text-(--text-primary)'
                    }`}
                  >
                    {tab.icon}
                    {tab.label}
                    <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                      ghTab === tab.key ? 'bg-primary-500/20 text-primary-400' : 'bg-(--bg-tertiary) text-(--text-tertiary)'
                    }`}>
                      {tab.count}
                    </span>
                  </button>
                ))}
              </div>

              {/* Repos Tab */}
              {ghTab === 'repos' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {ghData.repos.length === 0 ? (
                    <div className="col-span-2 text-center text-(--text-secondary) py-8">No repositories found.</div>
                  ) : ghData.repos.map(repo => (
                    <a key={repo.id} href={repo.html_url} target="_blank" rel="noopener noreferrer"
                      className="bg-(--bg-card) border border-(--border-default) rounded-xl p-4 hover:border-gray-500 transition-colors group">
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5">
                            <p className="font-medium text-(--text-primary) text-sm truncate group-hover:text-primary-400 transition-colors">
                              {repo.name}
                            </p>
                            {repo.private
                              ? <Lock size={11} className="text-(--text-tertiary) flex-shrink-0" />
                              : <Globe size={11} className="text-(--text-tertiary) flex-shrink-0" />
                            }
                          </div>
                          {repo.description && (
                            <p className="text-xs text-(--text-secondary) truncate mt-0.5">{repo.description}</p>
                          )}
                        </div>
                        <ExternalLink size={13} className="text-(--text-tertiary) group-hover:text-(--text-primary) transition-colors ml-2 flex-shrink-0" />
                      </div>
                      <div className="flex items-center gap-3 text-xs text-(--text-tertiary)">
                        {repo.language && (
                          <span className="flex items-center gap-1">
                            <span className="w-2 h-2 rounded-full flex-shrink-0"
                              style={{ background: LANG_COLORS[repo.language] || '#8b949e' }} />
                            {repo.language}
                          </span>
                        )}
                        <span className="flex items-center gap-1"><Star size={11} />{repo.stargazers_count}</span>
                        <span className="flex items-center gap-1"><GitFork size={11} />{repo.forks_count}</span>
                        {repo.open_issues_count > 0 && (
                          <span className="flex items-center gap-1"><AlertCircle size={11} />{repo.open_issues_count}</span>
                        )}
                        <span className="ml-auto">{timeAgo(repo.updated_at)}</span>
                      </div>
                    </a>
                  ))}
                </div>
              )}

              {/* Issues Tab */}
              {ghTab === 'issues' && (
                <div className="space-y-2">
                  {ghData.issues.length === 0 ? (
                    <div className="text-center text-(--text-secondary) py-8">No open issues assigned to you.</div>
                  ) : ghData.issues.map(issue => (
                    <a key={issue.id} href={issue.html_url} target="_blank" rel="noopener noreferrer"
                      className="flex items-start gap-3 bg-(--bg-card) border border-(--border-default) rounded-xl p-4 hover:border-gray-500 transition-colors group">
                      <AlertCircle size={16} className="text-green-500 mt-0.5 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-(--text-primary) group-hover:text-primary-400 transition-colors">
                          {issue.title}
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-xs text-(--text-tertiary)">{issue.repo} #{issue.number}</span>
                          {issue.labels.map(l => (
                            <span key={l} className="text-xs bg-primary-500/10 text-primary-400 px-1.5 py-0.5 rounded-full">{l}</span>
                          ))}
                        </div>
                      </div>
                      <div className="text-xs text-(--text-tertiary) flex-shrink-0">{timeAgo(issue.updated_at)}</div>
                    </a>
                  ))}
                </div>
              )}

              {/* PRs Tab */}
              {ghTab === 'prs' && (
                <div className="space-y-2">
                  {ghData.pull_requests.length === 0 ? (
                    <div className="text-center text-(--text-secondary) py-8">No open pull requests authored by you.</div>
                  ) : ghData.pull_requests.map(pr => (
                    <a key={pr.id} href={pr.html_url} target="_blank" rel="noopener noreferrer"
                      className="flex items-start gap-3 bg-(--bg-card) border border-(--border-default) rounded-xl p-4 hover:border-gray-500 transition-colors group">
                      <GitPullRequest size={16} className="text-purple-400 mt-0.5 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-(--text-primary) group-hover:text-primary-400 transition-colors">
                          {pr.title}
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-xs text-(--text-tertiary)">{pr.repo} #{pr.number}</span>
                          {pr.labels.map(l => (
                            <span key={l} className="text-xs bg-purple-500/10 text-purple-400 px-1.5 py-0.5 rounded-full">{l}</span>
                          ))}
                        </div>
                      </div>
                      <div className="text-xs text-(--text-tertiary) flex-shrink-0">{timeAgo(pr.updated_at)}</div>
                    </a>
                  ))}
                </div>
              )}
            </>
          ) : null}
        </div>
      )}

      {/* GitHub Setup Guide (when not connected) */}
      {!isGitHubConnected && (
        <div className="mt-2 bg-(--bg-card) border border-(--border-default) rounded-xl p-6 animate-fade-in">
          <div className="flex items-center gap-3 mb-3">
            <Github size={20} className="text-(--text-secondary)" />
            <h3 className="font-semibold text-(--text-primary)">Real GitHub Integration</h3>
          </div>
          <p className="text-sm text-(--text-secondary) mb-4">
            Connect your GitHub account to see your real repositories, open issues, and pull requests directly in your onboarding dashboard.
          </p>
          <div className="space-y-2 text-sm text-(--text-secondary)">
            <p className="flex items-center gap-2"><CheckCircle2 size={14} className="text-green-500" /> View your repos, issues & PRs in real-time</p>
            <p className="flex items-center gap-2"><CheckCircle2 size={14} className="text-green-500" /> GitHub OAuth 2.0 — secure, no password sharing</p>
            <p className="flex items-center gap-2"><CheckCircle2 size={14} className="text-green-500" /> Scopes: read:user, repo, read:org</p>
          </div>
          <div className="mt-4 p-3 bg-amber-500/5 border border-amber-500/20 rounded-lg text-xs text-amber-400">
            <strong>Setup required:</strong> Set <code>GITHUB_CLIENT_ID</code> and <code>GITHUB_CLIENT_SECRET</code> in <code>backend/.env</code>.
            Create a GitHub OAuth App at <a href="https://github.com/settings/applications/new" target="_blank" rel="noopener noreferrer" className="underline">github.com/settings/applications/new</a>.
          </div>
        </div>
      )}
    </div>
  );
};
