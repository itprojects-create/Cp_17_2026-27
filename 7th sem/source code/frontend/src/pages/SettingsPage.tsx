import React, { useEffect, useState } from 'react';
import {
  Moon,
  Sun,
  Mail,
  UserRound,
  ShieldCheck,
  Bell,
  Save,
  RotateCcw,
  Copy,
  LogOut,
  Sparkles,
  Cpu,
  RefreshCw,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuth } from '../contexts/useAuth';
import { useTheme } from '../contexts/useTheme';
import { api, type LLMStatus } from '../services/api';

const PROVIDER_LABELS: Record<string, string> = {
  nvidia: 'NVIDIA',
  gemini: 'Google Gemini',
  openai: 'OpenAI',
  grok: 'xAI Grok',
  anthropic: 'Anthropic',
  mock: 'Mock (offline)',
};
const providerLabel = (provider: string) => PROVIDER_LABELS[provider] ?? provider;

const statusStyle = (status?: string, health?: string) => {
  // A live check outranks configuration: a configured provider can still be out of quota.
  if (health === 'failing') return { label: 'Failing', classes: 'bg-red-500/10 text-red-500' };
  if (status === 'active') return { label: 'Operational', classes: 'bg-green-500/10 text-green-500' };
  if (status === 'fallback') return { label: 'Mock Fallback', classes: 'bg-amber-500/10 text-amber-500' };
  if (status === 'unavailable') return { label: 'Unavailable', classes: 'bg-red-500/10 text-red-500' };
  return { label: 'Unknown', classes: 'bg-gray-500/10 text-gray-500' };
};

type SettingsPrefs = {
  emailNotifications: boolean;
  checklistReminders: boolean;
  securityAlerts: boolean;
  weeklyDigest: boolean;
  autoStartLastSession: boolean;
  compactSidebar: boolean;
  timezone: string;
};

const DEFAULT_PREFS: SettingsPrefs = {
  emailNotifications: true,
  checklistReminders: true,
  securityAlerts: true,
  weeklyDigest: false,
  autoStartLastSession: true,
  compactSidebar: false,
  timezone: 'Asia/Kolkata',
};

export const SettingsPage: React.FC = () => {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [prefs, setPrefs] = useState<SettingsPrefs>(DEFAULT_PREFS);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [llmStatus, setLlmStatus] = useState<LLMStatus | null>(null);

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const [remote, llm] = await Promise.all([
          api.getSettings().catch(() => DEFAULT_PREFS),
          api.getLLMStatus(true).catch(() => null),
        ]);
        setPrefs({ ...DEFAULT_PREFS, ...remote });
        setLlmStatus(llm);
      } catch {
        toast.error('Unable to load settings, showing defaults');
        setPrefs(DEFAULT_PREFS);
      } finally {
        setIsLoading(false);
      }
    };
    loadSettings();
  }, []);

  const updatePref = <K extends keyof SettingsPrefs>(key: K, value: SettingsPrefs[K]) => {
    setPrefs((prev) => ({ ...prev, [key]: value }));
  };

  const savePreferences = async () => {
    try {
      setIsSaving(true);
      const saved = await api.updateSettings(prefs);
      setPrefs(saved);
      toast.success('Settings saved');
    } catch {
      toast.error('Unable to save settings');
    } finally {
      setIsSaving(false);
    }
  };

  const resetPreferences = async () => {
    try {
      setIsSaving(true);
      const saved = await api.updateSettings(DEFAULT_PREFS);
      setPrefs(saved);
      toast.success('Settings reset to defaults');
    } catch {
      toast.error('Unable to reset settings');
    } finally {
      setIsSaving(false);
    }
  };

  const copyEmail = async () => {
    if (!user?.email) return;
    try {
      await navigator.clipboard.writeText(user.email);
      toast.success('Email copied');
    } catch {
      toast.error('Unable to copy email');
    }
  };

  const RowToggle = ({
    label,
    description,
    checked,
    onChange,
  }: {
    label: string;
    description: string;
    checked: boolean;
    onChange: (value: boolean) => void;
  }) => (
    <div className="flex items-center justify-between rounded-lg border border-(--border-default) p-4 bg-(--bg-secondary)">
      <div>
        <p className="font-medium text-(--text-primary)">{label}</p>
        <p className="text-sm text-(--text-secondary)">{description}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative w-12 h-7 rounded-full transition-colors ${checked ? 'bg-primary-500' : 'bg-surface-500/40'}`}
      >
        <span
          className={`absolute top-1 left-1 w-5 h-5 rounded-full bg-white transition-transform ${checked ? 'translate-x-5' : ''}`}
        />
      </button>
    </div>
  );

  return (
    <div className="px-4 py-5 sm:p-6 md:p-8 max-w-4xl mx-auto space-y-6 animate-fade-in">
      {isLoading && (
        <div className="bg-(--bg-card) border border-(--border-default) rounded-xl p-4 text-sm text-(--text-secondary)">
          Loading your settings...
        </div>
      )}
      <div>
        <h1 className="text-2xl font-bold text-(--text-primary)">Settings</h1>
        <p className="text-sm text-(--text-secondary) mt-1">Manage your account preferences and application behavior.</p>
      </div>

      <div className="bg-(--bg-card) border border-(--border-default) rounded-xl p-6">
        <h2 className="text-lg font-semibold text-(--text-primary) mb-4">Account</h2>
        <div className="space-y-3">
          <div className="flex items-center gap-3 text-sm">
            <UserRound size={16} className="text-(--text-tertiary)" />
            <span className="text-(--text-secondary)">Username</span>
            <span className="ml-auto font-medium text-(--text-primary)">{user?.username || 'N/A'}</span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <Mail size={16} className="text-(--text-tertiary)" />
            <span className="text-(--text-secondary)">Email</span>
            <span className="ml-auto font-medium text-(--text-primary)">{user?.email || 'N/A'}</span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <ShieldCheck size={16} className="text-(--text-tertiary)" />
            <span className="text-(--text-secondary)">Account Status</span>
            <span className="ml-auto inline-flex items-center px-2 py-0.5 rounded-full bg-green-500/10 text-green-500 text-xs font-semibold">
              Active
            </span>
          </div>
        </div>
        <div className="mt-4">
          <button
            type="button"
            onClick={copyEmail}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-(--border-default) text-sm text-(--text-primary) hover:bg-(--bg-secondary) transition-colors"
          >
            <Copy size={15} />
            Copy Email
          </button>
        </div>
      </div>

      <div className="bg-(--bg-card) border border-(--border-default) rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <Sparkles size={18} className="text-primary-500" />
          <h2 className="text-lg font-semibold text-(--text-primary)">AI Engine & LLM</h2>
        </div>
        <div className="space-y-3">
          <div className="flex items-center gap-3 text-sm">
            <Cpu size={16} className="text-(--text-tertiary)" />
            <span className="text-(--text-secondary)">Provider</span>
            <span className="ml-auto font-medium text-(--text-primary)">
              {llmStatus ? providerLabel(llmStatus.provider) : 'Unknown'}
            </span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-(--text-tertiary) text-xs font-mono">ID</span>
            <span className="text-(--text-secondary)">Active Model</span>
            <span className="ml-auto font-mono text-xs text-primary-400 bg-primary-500/10 px-2 py-0.5 rounded truncate max-w-[60%]">
              {llmStatus?.model || '-'}
            </span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <ShieldCheck size={16} className="text-(--text-tertiary)" />
            <span className="text-(--text-secondary)">Engine Status</span>
            <span className={`ml-auto inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${statusStyle(llmStatus?.status, llmStatus?.health).classes}`}>
              {statusStyle(llmStatus?.status, llmStatus?.health).label}
            </span>
          </div>
          {llmStatus?.health === 'failing' && llmStatus.health_error && (
            <p className="text-xs text-red-500 text-right -mt-1">{llmStatus.health_error}</p>
          )}
          {llmStatus?.fallback && (
            <div className="flex items-center gap-3 text-sm">
              <RefreshCw size={16} className="text-(--text-tertiary)" />
              <span className="text-(--text-secondary)">Fallback</span>
              <span className="ml-auto text-xs text-(--text-primary) truncate max-w-[60%]">
                {providerLabel(llmStatus.fallback.provider)}
                <span className="font-mono text-(--text-tertiary)"> · {llmStatus.fallback.model}</span>
              </span>
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${statusStyle(llmStatus.fallback.status, llmStatus.fallback.health).classes}`}
                title={llmStatus.fallback.health_error ?? undefined}
              >
                {llmStatus.fallback.health === 'failing'
                  ? 'Failing'
                  : llmStatus.fallback.status === 'active' ? 'Ready' : statusStyle(llmStatus.fallback.status).label}
              </span>
            </div>
          )}
          {llmStatus?.fallback?.health === 'failing' && llmStatus.fallback.health_error && (
            <p className="text-xs text-red-500 text-right -mt-1">Fallback: {llmStatus.fallback.health_error}</p>
          )}
          {llmStatus?.error && (
            <p className="text-xs text-amber-500 bg-amber-500/10 rounded-lg px-3 py-2">{llmStatus.error}</p>
          )}
        </div>
      </div>

      <div className="bg-(--bg-card) border border-(--border-default) rounded-xl p-6">
        <h2 className="text-lg font-semibold text-(--text-primary) mb-4">Appearance</h2>
        <div className="space-y-3">
          <div className="flex items-center justify-between rounded-lg border border-(--border-default) p-4 bg-(--bg-secondary)">
            <div>
              <p className="font-medium text-(--text-primary)">Theme</p>
              <p className="text-sm text-(--text-secondary)">Switch between light and dark mode.</p>
            </div>
            <button
              onClick={toggleTheme}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors"
            >
              {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
              {theme === 'dark' ? 'Light mode' : 'Dark mode'}
            </button>
          </div>
          <RowToggle
            label="Compact Sidebar"
            description="Reduce sidebar spacing for more content area."
            checked={prefs.compactSidebar}
            onChange={(value) => updatePref('compactSidebar', value)}
          />
        </div>
      </div>

      <div className="bg-(--bg-card) border border-(--border-default) rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <Bell size={18} className="text-primary-500" />
          <h2 className="text-lg font-semibold text-(--text-primary)">Notifications</h2>
        </div>
        <div className="space-y-3">
          <RowToggle
            label="Email Notifications"
            description="Receive important onboarding updates in your inbox."
            checked={prefs.emailNotifications}
            onChange={(value) => updatePref('emailNotifications', value)}
          />
          <RowToggle
            label="Checklist Reminders"
            description="Get reminders when tasks are nearing deadlines."
            checked={prefs.checklistReminders}
            onChange={(value) => updatePref('checklistReminders', value)}
          />
          <RowToggle
            label="Security Alerts"
            description="Be notified when suspicious sign-in activity is detected."
            checked={prefs.securityAlerts}
            onChange={(value) => updatePref('securityAlerts', value)}
          />
          <RowToggle
            label="Weekly Digest"
            description="Receive a weekly summary of onboarding progress."
            checked={prefs.weeklyDigest}
            onChange={(value) => updatePref('weeklyDigest', value)}
          />
        </div>
      </div>

      <div className="bg-(--bg-card) border border-(--border-default) rounded-xl p-6">
        <h2 className="text-lg font-semibold text-(--text-primary) mb-4">Productivity</h2>
        <div className="space-y-3">
          <RowToggle
            label="Auto-open Last Session"
            description="Open your latest onboarding session when you log in."
            checked={prefs.autoStartLastSession}
            onChange={(value) => updatePref('autoStartLastSession', value)}
          />
          <div className="flex items-center justify-between rounded-lg border border-(--border-default) p-4 bg-(--bg-secondary)">
            <div>
              <p className="font-medium text-(--text-primary)">Timezone</p>
              <p className="text-sm text-(--text-secondary)">Used for deadlines and reminder timestamps.</p>
            </div>
            <select
              value={prefs.timezone}
              onChange={(e) => updatePref('timezone', e.target.value)}
              className="px-3 py-2 rounded-lg border border-(--border-default) bg-(--bg-card) text-sm text-(--text-primary) focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="Asia/Kolkata">Asia/Kolkata</option>
              <option value="UTC">UTC</option>
              <option value="America/New_York">America/New_York</option>
              <option value="Europe/London">Europe/London</option>
            </select>
          </div>
        </div>
      </div>

      <div className="bg-(--bg-card) border border-(--border-default) rounded-xl p-6">
        <h2 className="text-lg font-semibold text-(--text-primary) mb-4">Actions</h2>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={savePreferences}
            disabled={isSaving}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors"
          >
            <Save size={15} />
            {isSaving ? 'Saving...' : 'Save Settings'}
          </button>
          <button
            type="button"
            onClick={resetPreferences}
            disabled={isSaving}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-(--border-default) text-sm text-(--text-primary) hover:bg-(--bg-secondary) transition-colors"
          >
            <RotateCcw size={15} />
            Reset Defaults
          </button>
          <button
            type="button"
            onClick={logout}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-red-500/30 text-red-400 text-sm font-medium hover:bg-red-500/10 transition-colors"
          >
            <LogOut size={15} />
            Sign Out
          </button>
        </div>
      </div>
    </div>
  );
};
