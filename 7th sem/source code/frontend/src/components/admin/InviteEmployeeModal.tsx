import React, { useState } from 'react';
import { CheckCircle2, Mail, UserPlus, X } from 'lucide-react';
import { api } from '../../services/api';
import { getErrorDetail } from '../../services/errors';

interface InviteEmployeeModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** Called after a successful invite so the dashboard can show the new session. */
  onInvited: () => void;
}

export const InviteEmployeeModal: React.FC<InviteEmployeeModalProps> = ({ isOpen, onClose, onInvited }) => {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<{ email: string; emailSent: boolean } | null>(null);

  if (!isOpen) return null;

  const close = () => {
    setUsername('');
    setEmail('');
    setError('');
    setResult(null);
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);
    try {
      const data = await api.inviteEmployee({ username: username.trim(), email: email.trim() });
      setResult({ email: data.user.email, emailSent: data.email_sent });
      onInvited();
    } catch (err) {
      setError(getErrorDetail(err, 'Could not create the invitation. Please try again.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const inputClass =
    'w-full px-3 py-2.5 rounded-lg border border-(--border-default) bg-(--bg-secondary) text-(--text-primary) text-sm focus:outline-none focus:ring-2 focus:ring-primary-500';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-fade-in">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="invite-employee-title"
        className="relative w-full max-w-md bg-(--bg-card) border border-(--border-default) rounded-2xl shadow-2xl overflow-hidden animate-scale-up"
      >
        <div className="flex items-center justify-between p-6 border-b border-(--border-default)">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary-500/10 text-primary-500 flex items-center justify-center">
              <UserPlus size={20} />
            </div>
            <div>
              <h3 id="invite-employee-title" className="text-lg font-bold text-(--text-primary)">New Onboarding</h3>
              <p className="text-xs text-(--text-secondary)">Invite an employee to start onboarding</p>
            </div>
          </div>
          <button
            onClick={close}
            aria-label="Close"
            className="p-1.5 rounded-lg text-(--text-tertiary) hover:text-(--text-primary) hover:bg-(--bg-secondary) transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {result ? (
          <div className="p-6 space-y-4">
            <div className="flex items-start gap-3 p-4 rounded-xl bg-green-500/10 border border-green-500/20">
              <CheckCircle2 size={20} className="text-green-500 shrink-0 mt-0.5" />
              <div className="text-sm text-(--text-primary)">
                <p className="font-semibold">Onboarding created</p>
                <p className="text-(--text-secondary) mt-1">
                  {result.emailSent
                    ? `An invitation to set a password was sent to ${result.email}.`
                    : `The account was created, but the invitation email to ${result.email} could not be sent. They can use "Forgot password" on the sign-in page to set one.`}
                </p>
              </div>
            </div>
            <button
              onClick={close}
              className="w-full py-2.5 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors"
            >
              Done
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="p-6 space-y-4">
            <div>
              <label htmlFor="invite-username" className="block text-sm font-medium text-(--text-primary) mb-1.5">
                Username
              </label>
              <input
                id="invite-username"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="jane_doe"
                pattern="[A-Za-z0-9_\-]{3,32}"
                title="3-32 letters, digits, '_' or '-'"
                required
                autoFocus
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="invite-email" className="block text-sm font-medium text-(--text-primary) mb-1.5">
                Work email
              </label>
              <input
                id="invite-email"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="jane@novabyte.io"
                required
                className={inputClass}
              />
            </div>

            <p className="flex items-start gap-2 text-xs text-(--text-secondary)">
              <Mail size={14} className="shrink-0 mt-0.5" />
              They'll get an email with a link to set their password, then complete their profile to receive a personalized plan.
            </p>

            {error && (
              <p role="alert" className="text-sm text-red-500">{error}</p>
            )}

            <div className="flex gap-3 pt-1">
              <button
                type="button"
                onClick={close}
                className="flex-1 py-2.5 rounded-lg border border-(--border-default) text-(--text-primary) text-sm font-medium hover:bg-(--bg-secondary) transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="flex-1 py-2.5 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors disabled:opacity-60"
              >
                {isSubmitting ? 'Sending...' : 'Send invite'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
