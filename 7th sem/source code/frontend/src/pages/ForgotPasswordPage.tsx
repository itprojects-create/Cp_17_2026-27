import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Zap, Mail, ArrowLeft, CheckCircle } from 'lucide-react';
import { api } from '../services/api';
import toast from 'react-hot-toast';

export const ForgotPasswordPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      await api.requestPasswordReset(email);
      setSent(true);
      toast.success('Password reset link sent');
    } catch (error) {
      console.error(error);
      toast.error('Could not process reset request');
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
          {sent ? (
            <div className="text-center animate-fade-in">
              <div className="w-16 h-16 mx-auto rounded-full bg-green-500/10 flex items-center justify-center mb-4">
                <CheckCircle size={32} className="text-green-500" />
              </div>
              <h2 className="text-xl font-bold text-(--text-primary) mb-2">Check your email</h2>
              <p className="text-(--text-secondary) text-sm mb-6">If an account exists for this email, a reset link has been sent.</p>
              <Link to="/login" className="inline-flex items-center gap-2 text-sm text-primary-500 hover:text-primary-400 font-medium">
                <ArrowLeft size={16} /> Back to sign in
              </Link>
            </div>
          ) : (
            <>
              <h2 className="text-2xl font-bold text-(--text-primary) mb-1">Reset password</h2>
              <p className="text-(--text-secondary) text-sm mb-6">Enter your email and we'll send you a reset link</p>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-(--text-primary) mb-1.5">Email</label>
                  <div className="relative">
                    <Mail size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-(--text-tertiary)" />
                    <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="dev@company.com"
                      className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-(--border-default) bg-(--bg-secondary) text-(--text-primary) text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all" required />
                  </div>
                </div>
                <button type="submit" disabled={isLoading}
                  className="w-full py-2.5 rounded-lg bg-linear-to-r from-primary-600 to-primary-500 text-white font-medium text-sm hover:from-primary-500 hover:to-primary-400 transition-all disabled:opacity-60">
                  {isLoading ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin mx-auto" /> : 'Send Reset Link'}
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
