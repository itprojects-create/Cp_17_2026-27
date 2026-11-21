import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Zap, Eye, EyeOff, Mail, Lock, ArrowRight } from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../contexts/useAuth';
import { launchGoogleOAuth } from '../services/googleAuth';
import { GitHubSignInModal } from '../components/auth/GitHubSignInModal';
import toast from 'react-hot-toast';
import { getErrorDetail } from '../services/errors';

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isGitHubModalOpen, setIsGitHubModalOpen] = useState(false);

  const { login } = useAuth();
  
  const handleGoogleClick = () => {
    launchGoogleOAuth({
      onLoading: (loading) => setIsLoading(loading),
      onSuccess: (data) => {
        if (data && data.access_token) {
          localStorage.setItem('auth_token', data.access_token);
          login(data.access_token, data.user);
          toast.success(`Welcome back, ${data.user?.username || 'Developer'}!`);
          window.location.href = '/app/dashboard';
        }
      },
      onError: () => {
        setIsLoading(false);
      },

    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      // The API expects 'username' for OAuth2 password grant. We'll send email as username.
      const data = await api.login({ username: email, password });
      if (data && data.access_token) {
        // Fetch user info using the token
        localStorage.setItem('auth_token', data.access_token);
        const userData = await api.getMe();
        login(data.access_token, userData);
        toast.success("Welcome back!");
        window.location.href = '/app/dashboard';
      }
    } catch (error) {
      toast.error(getErrorDetail(error, "Invalid credentials"));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-(--bg-primary)">
      {/* GitHub OAuth Modal */}
      <GitHubSignInModal
        isOpen={isGitHubModalOpen}
        onClose={() => setIsGitHubModalOpen(false)}
      />


      {/* Left Panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-linear-to-br from-surface-900 via-surface-800 to-primary-900 relative overflow-hidden items-center justify-center p-12">
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-20 left-20 w-72 h-72 bg-primary-500 rounded-full blur-3xl" />
          <div className="absolute bottom-20 right-20 w-96 h-96 bg-accent-500 rounded-full blur-3xl" />
        </div>
        <div className="relative z-10 text-center max-w-md">
          <div className="w-16 h-16 mx-auto rounded-2xl bg-linear-to-br from-primary-500 to-accent-500 flex items-center justify-center mb-8">
            <Zap size={32} className="text-white" />
          </div>
          <h1 className="text-4xl font-bold text-white mb-4">NovaByte</h1>
          <p className="text-lg text-surface-300">AI-powered developer onboarding that gets your team productive in days, not weeks.</p>
          <div className="mt-12 grid grid-cols-3 gap-4 text-center">
            {[
              { value: '3x', label: 'Faster Onboarding' },
              { value: '95%', label: 'Completion Rate' },
              { value: '500+', label: 'Developers' },
            ].map(s => (
              <div key={s.label}>
                <div className="text-2xl font-bold text-white">{s.value}</div>
                <div className="text-xs text-surface-400 mt-1">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right Panel - Form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md animate-fade-in">
          <div className="lg:hidden flex items-center gap-2 mb-8 justify-center">
            <div className="w-10 h-10 rounded-xl bg-linear-to-br from-primary-500 to-accent-500 flex items-center justify-center">
              <Zap size={20} className="text-white" />
            </div>
            <span className="text-xl font-bold text-(--text-primary)">NovaByte</span>
          </div>

          <h2 className="text-2xl font-bold text-(--text-primary) mb-1">Welcome back</h2>
          <p className="text-(--text-secondary) mb-8">Sign in to continue your onboarding journey</p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-(--text-primary) mb-1.5">Email</label>
              <div className="relative">
                <Mail size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-(--text-tertiary)" />
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="dev@company.com"
                  className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-(--border-default) bg-(--bg-secondary) text-(--text-primary) text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all"
                  required
                />
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-sm font-medium text-(--text-primary)">Password</label>
                <Link to="/forgot-password" className="text-xs text-primary-500 hover:text-primary-400">Forgot password?</Link>
              </div>
              <div className="relative">
                <Lock size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-(--text-tertiary)" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-10 pr-10 py-2.5 rounded-lg border border-(--border-default) bg-(--bg-secondary) text-(--text-primary) text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-(--text-tertiary) hover:text-(--text-secondary)"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>
            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-linear-to-r from-primary-600 to-primary-500 text-white font-medium text-sm hover:from-primary-500 hover:to-primary-400 transition-all disabled:opacity-60 shadow-lg shadow-primary-500/20 cursor-pointer"
            >
              {isLoading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>Sign In <ArrowRight size={16} /></>
              )}
            </button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-sm text-(--text-secondary)">
              Don't have an account? <Link to="/signup" className="text-primary-500 hover:text-primary-400 font-medium">Sign up</Link>
            </p>
          </div>

          <div className="mt-8 flex items-center gap-3">
            <div className="flex-1 h-px bg-(--border-default)" />
            <span className="text-xs text-(--text-tertiary)">or continue with</span>
            <div className="flex-1 h-px bg-(--border-default)" />
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setIsGitHubModalOpen(true)}
              className="flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg border border-(--border-default) bg-(--bg-secondary) text-sm font-medium text-(--text-primary) hover:bg-(--bg-tertiary) hover:border-primary-500/30 transition-colors cursor-pointer"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24"><path fill="currentColor" d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
              GitHub
            </button>
            <button
              type="button"
              onClick={handleGoogleClick}
              className="flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg border border-(--border-default) bg-(--bg-secondary) text-sm font-medium text-(--text-primary) hover:bg-(--bg-tertiary) hover:border-primary-500/30 transition-colors cursor-pointer"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
              Google
            </button>

          </div>
        </div>
      </div>
    </div>
  );
};

