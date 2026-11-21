import React, { useState } from 'react';
import { X, ArrowRight, GitBranch, Sparkles } from 'lucide-react';
import { api } from '../../services/api';
import { useAuth } from '../../contexts/useAuth';
import toast from 'react-hot-toast';
import { getErrorDetail } from '../../services/errors';

interface GitHubSignInModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const GITHUB_DEMO_ACCOUNTS = [
  {
    username: 'octodev-lead',
    name: 'Devin Octo',
    email: 'octodev@github.com',
    role: 'Core Contributor',
  },
  {
    username: 'harsh-craft',
    name: 'Harsh CodeCraft',
    email: 'harsh.dev@github.com',
    role: 'Fullstack Engineer',
  },
];

export const GitHubSignInModal: React.FC<GitHubSignInModalProps> = ({ isOpen, onClose }) => {
  const [customUsername, setCustomUsername] = useState('');
  const [showCustomInput, setShowCustomInput] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const { login } = useAuth();

  if (!isOpen) return null;

  const handleGitHubLogin = async (username: string, name?: string, email?: string) => {
    setIsLoading(true);
    try {
      const data = await api.githubLogin({ username, name, email });
      if (data && data.access_token) {
        localStorage.setItem('auth_token', data.access_token);
        const userData = await api.getMe();
        login(data.access_token, userData);
        toast.success(`Signed in as @${username} via GitHub!`);
        onClose();
        window.location.href = '/app/dashboard';
      }
    } catch (error) {
      toast.error(getErrorDetail(error, 'Failed to authenticate with GitHub'));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-fade-in">
      <div className="relative w-full max-w-md bg-(--bg-card) border border-(--border-default) rounded-2xl shadow-2xl overflow-hidden animate-scale-up">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-(--border-default)">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gray-900 text-white border border-(--border-default) flex items-center justify-center shadow-xs">
              <svg className="w-5 h-5" viewBox="0 0 24 24"><path fill="currentColor" d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
            </div>
            <div>
              <h3 className="text-lg font-bold text-(--text-primary)">Sign in with GitHub</h3>
              <p className="text-xs text-(--text-secondary)">Link your GitHub developer identity</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-(--text-tertiary) hover:text-(--text-primary) hover:bg-(--bg-secondary) transition-colors">
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4">
          <div className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-primary-500/10 border border-primary-500/20 text-primary-400 text-xs font-medium">
            <Sparkles size={14} className="shrink-0" />
            <span>Fast GitHub Developer OAuth</span>
          </div>

          <div className="space-y-2">
            {GITHUB_DEMO_ACCOUNTS.map((acc) => (
              <button
                key={acc.username}
                type="button"
                disabled={isLoading}
                onClick={() => handleGitHubLogin(acc.username, acc.name, acc.email)}
                className="w-full flex items-center justify-between p-3.5 rounded-xl border border-(--border-default) bg-(--bg-secondary) hover:bg-(--bg-tertiary) hover:border-primary-500/50 transition-all text-left group disabled:opacity-60"
              >
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full bg-gray-800 text-white font-bold flex items-center justify-center text-sm">
                    <GitBranch size={16} />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-(--text-primary)">{acc.name}</div>
                    <div className="text-xs text-(--text-secondary)">@{acc.username}</div>
                  </div>
                </div>
                <ArrowRight size={16} className="text-(--text-tertiary) group-hover:text-primary-500 group-hover:translate-x-0.5 transition-all" />
              </button>
            ))}
          </div>

          {!showCustomInput ? (
            <button
              type="button"
              onClick={() => setShowCustomInput(true)}
              className="w-full py-2 text-center text-xs font-medium text-primary-500 hover:text-primary-400 hover:underline transition-colors"
            >
              + Use custom GitHub username
            </button>
          ) : (
            <form onSubmit={(e) => { e.preventDefault(); if (customUsername) handleGitHubLogin(customUsername); }} className="pt-2 border-t border-(--border-default) space-y-3">
              <div>
                <label className="block text-xs font-medium text-(--text-secondary) mb-1">GitHub Username</label>
                <input
                  type="text"
                  value={customUsername}
                  onChange={(e) => setCustomUsername(e.target.value)}
                  placeholder="e.g. torvalds"
                  className="w-full px-3 py-2 rounded-lg border border-(--border-default) bg-(--bg-secondary) text-(--text-primary) text-xs focus:outline-none focus:ring-2 focus:ring-primary-500"
                  required
                />
              </div>
              <button
                type="submit"
                disabled={isLoading}
                className="w-full flex items-center justify-center gap-2 py-2 px-4 rounded-lg bg-gray-900 hover:bg-gray-800 text-white font-medium text-xs transition-colors shadow-xs disabled:opacity-60"
              >
                {isLoading ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <>Continue as @{customUsername || 'username'} <ArrowRight size={14} /></>
                )}
              </button>
            </form>
          )}
        </div>

        <div className="px-6 py-3.5 bg-(--bg-secondary)/50 border-t border-(--border-default) flex items-center justify-between text-2xs text-(--text-tertiary)">
          <span>Secured with GitHub OAuth</span>
          <span>Terms & Privacy</span>
        </div>
      </div>
    </div>
  );
};
