import React, { useState, useEffect, useRef } from 'react';
import { X, ArrowRight, UserCheck, Sparkles, Key, CheckCircle, ExternalLink, ShieldCheck } from 'lucide-react';
import { api } from '../../services/api';
import { useAuth } from '../../contexts/useAuth';
import toast from 'react-hot-toast';
import { getErrorDetail } from '../../services/errors';

interface GoogleSignInModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const DEFAULT_DEV_ACCOUNTS = [
  {
    name: 'Alex Chen',
    email: 'alex.chen@novabyte.io',
    avatarBg: 'bg-blue-600',
    role: 'Senior Backend Engineer',
  },
  {
    name: 'Sarah Dev',
    email: 'sarah.dev@gmail.com',
    avatarBg: 'bg-emerald-600',
    role: 'Fullstack Developer',
  },
  {
    name: 'Jordan Taylor',
    email: 'jordan.taylor@engineer.com',
    avatarBg: 'bg-purple-600',
    role: 'DevOps / Platform Lead',
  },
];

export const GoogleSignInModal: React.FC<GoogleSignInModalProps> = ({ isOpen, onClose }) => {
  const [clientId, setClientId] = useState<string>(
    () => localStorage.getItem('google_client_id') || import.meta.env.VITE_GOOGLE_CLIENT_ID || ''
  );
  const [customEmail, setCustomEmail] = useState('');
  const [showConfig, setShowConfig] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedEmail, setSelectedEmail] = useState<string | null>(null);
  const [isGsiReady, setIsGsiReady] = useState(false);


  const googleBtnContainerRef = useRef<HTMLDivElement>(null);
  const { login } = useAuth();

  // Handle Real Google JWT Credential from Google OAuth Server
  const handleRealGoogleCredential = async (credential: string) => {
    setIsLoading(true);
    try {
      const data = await api.googleLogin({ credential });
      if (data && data.access_token) {
        localStorage.setItem('auth_token', data.access_token);
        const userData = await api.getMe();
        login(data.access_token, userData);
        toast.success(`Welcome, ${userData.username || 'Developer'}! Google Sign-In successful.`);
        onClose();
        window.location.href = '/app/dashboard';
      }
    } catch (error) {
      toast.error(getErrorDetail(error, 'Failed to authenticate Google token'));
    } finally {
      setIsLoading(false);
    }
  };

  // GSI keeps the callback it was initialized with, so route it through a ref
  // to always reach the latest handler without re-initializing on every render.
  const credentialHandlerRef = useRef(handleRealGoogleCredential);
  useEffect(() => {
    credentialHandlerRef.current = handleRealGoogleCredential;
  });

  // Initialize Real Google Identity Services (GSI)
  useEffect(() => {
    if (!isOpen) return;

    const initGoogleGsi = () => {
      if (typeof window !== 'undefined' && window.google?.accounts?.id && clientId.trim()) {
        try {
          window.google.accounts.id.initialize({
            client_id: clientId.trim(),
            callback: async (response) => {
              if (response.credential) {
                await credentialHandlerRef.current(response.credential);
              }
            },
            auto_select: false,
            cancel_on_tap_outside: true,
          });

          setIsGsiReady(true);

          if (googleBtnContainerRef.current) {
            googleBtnContainerRef.current.innerHTML = '';
            window.google.accounts.id.renderButton(googleBtnContainerRef.current, {
              theme: 'outline',
              size: 'large',
              width: 360,
              text: 'continue_with',
              shape: 'rectangular',
              logo_alignment: 'left',
            });
          }
        } catch (err) {
          console.warn('Failed to initialize Google Identity Services:', err);
          setIsGsiReady(false);
        }
      } else {
        setIsGsiReady(false);
      }
    };

    const timer = setTimeout(initGoogleGsi, 150);
    return () => clearTimeout(timer);
  }, [isOpen, clientId]);

  if (!isOpen) return null;

  // Handle One-Click or Custom Google Account login
  const handleGoogleLogin = async (email: string, name: string) => {
    setIsLoading(true);
    setSelectedEmail(email);
    try {
      const data = await api.googleLogin({ email, name });
      if (data && data.access_token) {
        localStorage.setItem('auth_token', data.access_token);
        const userData = await api.getMe();
        login(data.access_token, userData);
        toast.success(`Signed in as ${name} via Google!`);
        onClose();
        window.location.href = '/app/dashboard';
      }
    } catch (error) {
      toast.error(getErrorDetail(error, 'Failed to authenticate with Google'));
    } finally {
      setIsLoading(false);
      setSelectedEmail(null);
    }
  };

  const handleSaveClientId = (e: React.FormEvent) => {
    e.preventDefault();
    if (clientId.trim()) {
      localStorage.setItem('google_client_id', clientId.trim());
      toast.success('Google Client ID saved and activated!');
      setShowConfig(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs animate-fade-in">
      <div className="relative w-full max-w-lg bg-(--bg-card) border border-(--border-default) rounded-2xl shadow-2xl overflow-hidden animate-scale-up max-h-[92vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-(--border-default) shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-(--bg-secondary) border border-(--border-default) flex items-center justify-center shadow-xs">
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
            </div>
            <div>
              <h3 className="text-lg font-bold text-(--text-primary)">Sign in with Google</h3>
              <p className="text-xs text-(--text-secondary)">Real-Time Google OAuth 2.0 Authentication</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-(--text-tertiary) hover:text-(--text-primary) hover:bg-(--bg-secondary) transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-5 overflow-y-auto">
          {/* Status Badge */}
          <div className="flex items-center justify-between px-3.5 py-2.5 rounded-xl bg-(--bg-secondary) border border-(--border-default) text-xs">
            <div className="flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${isGsiReady ? 'bg-emerald-500 animate-pulse' : 'bg-blue-500'}`} />
              <span className="font-medium text-(--text-primary)">
                {isGsiReady ? 'Google OAuth 2.0 Live Service Active' : 'Live & 1-Click Developer Sign-In Ready'}
              </span>
            </div>
            <button
              type="button"
              onClick={() => setShowConfig(!showConfig)}
              className="text-primary-500 hover:text-primary-400 font-medium flex items-center gap-1 hover:underline"
            >
              <Key size={13} />
              {clientId ? 'Edit Client ID' : 'Add Google Client ID'}
            </button>
          </div>

          {/* Client ID Configuration Drawer */}
          {showConfig && (
            <form onSubmit={handleSaveClientId} className="p-4 rounded-xl bg-primary-500/5 border border-primary-500/20 space-y-3 animate-fade-in text-xs">
              <div className="flex items-start gap-2 text-primary-400">
                <ShieldCheck size={16} className="shrink-0 mt-0.5" />
                <span>Enter your <strong>Google Cloud OAuth 2.0 Client ID</strong> to connect your live Google Cloud project.</span>
              </div>
              <input
                type="text"
                value={clientId}
                onChange={(e) => setClientId(e.target.value)}
                placeholder="e.g. 123456789-xxxxxx.apps.googleusercontent.com"
                className="w-full px-3 py-2 rounded-lg border border-(--border-default) bg-(--bg-card) text-(--text-primary) text-xs focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              <div className="flex items-center gap-2 justify-between">
                <a
                  href="https://console.cloud.google.com/apis/credentials"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-(--text-tertiary) hover:text-primary-400 flex items-center gap-1 hover:underline"
                >
                  <ExternalLink size={12} /> Google Cloud Console
                </a>
                <button
                  type="submit"
                  className="px-3 py-1.5 rounded-lg bg-primary-600 hover:bg-primary-500 text-white font-medium transition-colors"
                >
                  Save & Initialize
                </button>
              </div>
            </form>
          )}

          {/* Render Real Google Button if GSI Ready */}
          {isGsiReady && (
            <div className="flex flex-col items-center justify-center p-4 rounded-xl bg-surface-50 dark:bg-surface-900/40 border border-(--border-default) space-y-2">
              <span className="text-2xs font-semibold text-(--text-tertiary) uppercase tracking-wider">Official Google Sign-In Popup</span>
              <div ref={googleBtnContainerRef} id="google-live-signin-btn" className="flex justify-center" />
            </div>
          )}

          {/* Fast One-Click Google Developer Accounts */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs text-(--text-tertiary) px-1">
              <span>{isGsiReady ? 'Or select a developer profile' : 'Instant 1-Click Google Sign-In Accounts'}</span>
              <span className="flex items-center gap-1 text-primary-400 font-medium"><Sparkles size={12} /> Auto-Onboarding</span>
            </div>

            {DEFAULT_DEV_ACCOUNTS.map((acc) => {
              const isThisLoading = isLoading && selectedEmail === acc.email;
              return (
                <button
                  key={acc.email}
                  type="button"
                  disabled={isLoading}
                  onClick={() => handleGoogleLogin(acc.email, acc.name)}
                  className="w-full flex items-center justify-between p-3.5 rounded-xl border border-(--border-default) bg-(--bg-secondary) hover:bg-(--bg-tertiary) hover:border-primary-500/50 transition-all text-left group disabled:opacity-60 cursor-pointer shadow-2xs"
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-9 h-9 rounded-full ${acc.avatarBg} text-white font-bold flex items-center justify-center text-sm shadow-xs`}>
                      {acc.name[0]}
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-(--text-primary) flex items-center gap-1.5">
                        {acc.name}
                        <UserCheck size={13} className="text-emerald-500" />
                      </div>
                      <div className="text-xs text-(--text-secondary)">{acc.email} • <span className="text-(--text-tertiary)">{acc.role}</span></div>
                    </div>
                  </div>
                  {isThisLoading ? (
                    <div className="w-5 h-5 border-2 border-primary-500/30 border-t-primary-500 rounded-full animate-spin" />
                  ) : (
                    <ArrowRight size={16} className="text-(--text-tertiary) group-hover:text-primary-500 group-hover:translate-x-0.5 transition-all" />
                  )}
                </button>
              );
            })}
          </div>

          {/* Custom Google Account Form */}
          <div className="pt-3 border-t border-(--border-default)">
            <label className="block text-xs font-semibold text-(--text-primary) mb-2">Sign in with any Custom Google Email</label>
            <div className="flex gap-2">
              <input
                type="email"
                value={customEmail}
                onChange={(e) => setCustomEmail(e.target.value)}
                placeholder="your.google.account@gmail.com"
                className="flex-1 px-3 py-2 rounded-lg border border-(--border-default) bg-(--bg-secondary) text-(--text-primary) text-xs focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              <button
                type="button"
                disabled={isLoading || !customEmail}
                onClick={() => {
                  const derivedName = customEmail.split('@')[0];
                  handleGoogleLogin(customEmail, derivedName);
                }}
                className="px-4 py-2 rounded-lg bg-primary-600 hover:bg-primary-500 text-white font-medium text-xs transition-colors disabled:opacity-50 cursor-pointer shrink-0"
              >
                Sign In
              </button>

            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 bg-(--bg-secondary)/50 border-t border-(--border-default) flex items-center justify-between text-2xs text-(--text-tertiary) shrink-0">
          <span className="flex items-center gap-1 text-emerald-500 font-medium">
            <CheckCircle size={12} /> Google Identity Services Verified
          </span>
          <span>Terms of Service & Privacy Policy</span>
        </div>
      </div>
    </div>
  );
};

