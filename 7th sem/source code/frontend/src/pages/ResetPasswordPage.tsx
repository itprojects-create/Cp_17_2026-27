import React, { useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Zap, Lock, Eye, EyeOff, ArrowLeft, CheckCircle, AlertTriangle } from 'lucide-react';
import { api } from '../services/api';
import toast from 'react-hot-toast';
import { getErrorDetail } from '../services/errors';

export const ResetPasswordPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const token = useMemo(() => (searchParams.get('token') || '').trim(), [searchParams]);

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isDone, setIsDone] = useState(false);

  const hasToken = token.length > 0;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (password.length < 8) {
      toast.error('Password must be at least 8 characters');
      return;
    }

    if (password !== confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }

    if (!hasToken) {
      toast.error('Invalid reset link');
      return;
    }

    setIsLoading(true);
    try {
      await api.resetPassword(token, password);
      setIsDone(true);
      toast.success('Password updated successfully');
      setTimeout(() => navigate('/login'), 1200);
    } catch (error) {
      console.error(error);
      toast.error(getErrorDetail(error, 'Invalid or expired reset link'));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-(--bg-primary) p-4">
      <div className="w-full max-w-md animate-fade-in">
        <div className="flex items-center gap-2 mb-8 justify-center">
          <div className="w-10 h-10 rounded-xl bg-linear-to-br from-primary-500 to-accent-500 flex items-center justify-center">
            <Zap size={20} className="text-white" />
          </div>
          <span className="text-xl font-bold text-(--text-primary)">NovaByte</span>
        </div>

        <div className="bg-(--bg-card) border border-(--border-default) rounded-2xl p-8 shadow-lg">
          {!hasToken ? (
            <div className="text-center animate-fade-in">
              <div className="w-16 h-16 mx-auto rounded-full bg-red-500/10 flex items-center justify-center mb-4">
                <AlertTriangle size={30} className="text-red-500" />
              </div>
              <h2 className="text-xl font-bold text-(--text-primary) mb-2">Invalid reset link</h2>
              <p className="text-(--text-secondary) text-sm mb-6">This password reset link is missing a token.</p>
              <Link to="/forgot-password" className="inline-flex items-center gap-2 text-sm text-primary-500 hover:text-primary-400 font-medium">
                Request a new link
              </Link>
            </div>
          ) : isDone ? (
            <div className="text-center animate-fade-in">
              <div className="w-16 h-16 mx-auto rounded-full bg-green-500/10 flex items-center justify-center mb-4">
                <CheckCircle size={32} className="text-green-500" />
              </div>
              <h2 className="text-xl font-bold text-(--text-primary) mb-2">Password updated</h2>
              <p className="text-(--text-secondary) text-sm mb-6">You can now sign in with your new password.</p>
              <Link to="/login" className="inline-flex items-center gap-2 text-sm text-primary-500 hover:text-primary-400 font-medium">
                <ArrowLeft size={16} /> Back to sign in
              </Link>
            </div>
          ) : (
            <>
              <h2 className="text-2xl font-bold text-(--text-primary) mb-1">Set new password</h2>
              <p className="text-(--text-secondary) text-sm mb-6">Choose a secure password for your account</p>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-(--text-primary) mb-1.5">New password</label>
                  <div className="relative">
                    <Lock size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-(--text-tertiary)" />
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Minimum 8 characters"
                      className="w-full pl-10 pr-10 py-2.5 rounded-lg border border-(--border-default) bg-(--bg-secondary) text-(--text-primary) text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all"
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

                <div>
                  <label className="block text-sm font-medium text-(--text-primary) mb-1.5">Confirm new password</label>
                  <div className="relative">
                    <Lock size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-(--text-tertiary)" />
                    <input
                      type={showConfirmPassword ? 'text' : 'password'}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Re-enter new password"
                      className="w-full pl-10 pr-10 py-2.5 rounded-lg border border-(--border-default) bg-(--bg-secondary) text-(--text-primary) text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all"
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-(--text-tertiary) hover:text-(--text-secondary)"
                    >
                      {showConfirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full py-2.5 rounded-lg bg-linear-to-r from-primary-600 to-primary-500 text-white font-medium text-sm hover:from-primary-500 hover:to-primary-400 transition-all disabled:opacity-60"
                >
                  {isLoading ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin mx-auto" /> : 'Update Password'}
                </button>
              </form>

              <p className="mt-6 text-center">
                <Link to="/login" className="inline-flex items-center gap-1 text-sm text-(--text-secondary) hover:text-(--text-primary)">
                  <ArrowLeft size={14} /> Back to sign in
                </Link>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
