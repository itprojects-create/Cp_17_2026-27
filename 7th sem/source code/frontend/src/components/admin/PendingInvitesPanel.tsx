import React, { useCallback, useEffect, useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { Clock, MailWarning, RotateCw, Send, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { api } from '../../services/api';
import { getErrorDetail } from '../../services/errors';
import type { PendingInvite } from '../../types';

interface PendingInvitesPanelProps {
  /** Bump to reload, e.g. after a new invite is sent. */
  version: number;
  /** Called after a cancel, since it also removes the onboarding session from the table. */
  onChanged: () => void;
}

const ago = (iso: string) => formatDistanceToNow(new Date(iso), { addSuffix: true });

export const PendingInvitesPanel: React.FC<PendingInvitesPanelProps> = ({ version, onChanged }) => {
  const [invites, setInvites] = useState<PendingInvite[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [confirmingId, setConfirmingId] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      setInvites(await api.getPendingInvites());
    } catch (e) {
      console.error('Failed to load pending invites:', e);
    }
  }, []);

  useEffect(() => { load(); }, [load, version]);

  const resend = async (invite: PendingInvite) => {
    setBusyId(invite.user_id);
    try {
      const updated = await api.resendInvite(invite.user_id);
      setInvites(prev => prev.map(i => (i.user_id === invite.user_id ? updated : i)));
      if (updated.email_sent) toast.success(`New invite sent to ${invite.email}`);
      else toast.error(`A new link was created, but the email to ${invite.email} could not be sent.`);
    } catch (e) {
      toast.error(getErrorDetail(e, 'Could not resend the invite.'));
    } finally {
      setBusyId(null);
    }
  };

  const cancel = async (invite: PendingInvite) => {
    setBusyId(invite.user_id);
    try {
      await api.cancelInvite(invite.user_id);
      setInvites(prev => prev.filter(i => i.user_id !== invite.user_id));
      toast.success(`Invite for ${invite.username} cancelled`);
      onChanged();
    } catch (e) {
      toast.error(getErrorDetail(e, 'Could not cancel the invite.'));
    } finally {
      setBusyId(null);
      setConfirmingId(null);
    }
  };

  if (invites.length === 0) return null;
  const expiredCount = invites.filter(i => i.status === 'expired').length;

  return (
    <section className="bg-(--bg-card) border border-(--border-default) rounded-xl mb-8 shadow-xs overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 sm:px-5 py-4 border-b border-(--border-default)">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-(--text-primary)">
          <MailWarning size={16} className="text-amber-500" />
          Pending invites ({invites.length})
        </h2>
        <p className="text-xs text-(--text-secondary)">
          {expiredCount > 0 ? `${expiredCount} expired. Resend to send a fresh link.` : "Waiting for these employees to set a password."}
        </p>
      </div>
      <ul className="divide-y divide-(--border-default)">
        {invites.map(invite => {
          const busy = busyId === invite.user_id;
          return (
            <li key={invite.user_id} className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-4 sm:px-5 py-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-(--text-primary) truncate">
                  {invite.username} <span className="font-normal text-(--text-secondary)">· {invite.email}</span>
                </p>
                <p className="flex flex-wrap items-center gap-x-2 text-xs text-(--text-tertiary) mt-0.5">
                  <span>Invited {ago(invite.invited_at)}{invite.invited_by && ` by ${invite.invited_by}`}</span>
                  {invite.status === 'expired' ? (
                    <span className="inline-flex items-center gap-1 text-red-500"><Clock size={12} /> Link expired</span>
                  ) : invite.expires_at && (
                    <span className="inline-flex items-center gap-1"><Clock size={12} /> Link expires {ago(invite.expires_at)}</span>
                  )}
                </p>
              </div>

              {confirmingId === invite.user_id ? (
                <div className="flex items-center gap-2 text-sm shrink-0">
                  <span className="text-(--text-secondary)">Delete this account?</span>
                  <button onClick={() => cancel(invite)} disabled={busy}
                    className="px-3 py-1.5 rounded-lg bg-red-500 text-white text-xs font-medium hover:bg-red-600 transition-colors disabled:opacity-60">
                    {busy ? 'Cancelling...' : 'Cancel invite'}
                  </button>
                  <button onClick={() => setConfirmingId(null)} disabled={busy}
                    className="px-3 py-1.5 rounded-lg border border-(--border-default) text-(--text-primary) text-xs font-medium hover:bg-(--bg-secondary) transition-colors">
                    Keep
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2 shrink-0">
                  <button onClick={() => resend(invite)} disabled={busy}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-(--border-default) text-(--text-primary) text-xs font-medium hover:bg-(--bg-secondary) transition-colors disabled:opacity-60">
                    {busy ? <RotateCw size={14} className="animate-spin" /> : <Send size={14} />} Resend
                  </button>
                  <button onClick={() => setConfirmingId(invite.user_id)} disabled={busy}
                    aria-label={`Cancel invite for ${invite.username}`}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-red-500/30 text-red-500 text-xs font-medium hover:bg-red-500/10 transition-colors disabled:opacity-60">
                    <X size={14} /> Cancel
                  </button>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
};
