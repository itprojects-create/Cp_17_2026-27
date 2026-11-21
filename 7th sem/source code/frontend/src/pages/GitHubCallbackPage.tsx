/**
 * GitHubCallbackPage
 */
import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Github, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { api } from '../services/api';

type Stage = 'loading' | 'success' | 'error';

export const GitHubCallbackPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const code = searchParams.get('code') || '';
  const oauthState = searchParams.get('state') || '';
  const oauthError = searchParams.get('error') || '';
  // URL problems are known on first render, so start in the error stage directly.
  const initialError = oauthError
    ? (oauthError === 'access_denied' ? 'You cancelled the GitHub authorization.' : `GitHub error: ${oauthError}`)
    : (!code ? 'No OAuth code received from GitHub.' : '');
  const [stage, setStage] = useState<Stage>(initialError ? 'error' : 'loading');
  const [message, setMessage] = useState(initialError);
  const [ghUser, setGhUser] = useState<{ login: string; avatar: string } | null>(null);
  // OAuth codes are single-use; StrictMode's double effect run must not exchange twice.
  const exchangeStarted = useRef(false);

  useEffect(() => {
    if (initialError) {
      const timer = setTimeout(() => navigate('/app/integrations'), 3000);
      return () => clearTimeout(timer);
    }
    if (exchangeStarted.current) return;
    exchangeStarted.current = true;

    api.handleGitHubOAuthCallback(code, oauthState)
      .then((data) => {
        setGhUser({ login: data.github_username, avatar: data.github_avatar });
        setStage('success');
        setMessage(`Successfully connected as @${data.github_username}`);
        setTimeout(() => navigate('/app/integrations?github=connected'), 2500);
      })
      .catch((err) => {
        const detail = err?.response?.data?.detail || err?.message || 'Unknown error';
        setStage('error');
        setMessage(detail);
        setTimeout(() => navigate('/app/integrations?github=error'), 3000);
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: '#0f1117' }}>
      <div style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 24, padding: 40, maxWidth: 360, width: '100%', textAlign: 'center' }}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 24 }}>
          {stage === 'loading' && (
            <div style={{ width: 64, height: 64, borderRadius: 16, background: '#1e2330', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Github size={32} color="#fff" />
            </div>
          )}
          {stage === 'success' && (
            ghUser?.avatar ? (
              <img src={ghUser.avatar} alt="avatar"
                style={{ width: 64, height: 64, borderRadius: 16, border: '3px solid rgba(34,197,94,0.5)' }} />
            ) : (
              <div style={{ width: 64, height: 64, borderRadius: 16, background: 'rgba(34,197,94,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <CheckCircle2 size={32} color="#4ade80" />
              </div>
            )
          )}
          {stage === 'error' && (
            <div style={{ width: 64, height: 64, borderRadius: 16, background: 'rgba(239,68,68,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <XCircle size={32} color="#f87171" />
            </div>
          )}
        </div>

        {stage === 'loading' && (
          <>
            <Loader2 size={20} style={{ animation: 'spin 1s linear infinite', color: '#818cf8', margin: '0 auto 12px' }} />
            <h2 style={{ color: '#fff', fontSize: 18, fontWeight: 600, marginBottom: 6 }}>Connecting to GitHub...</h2>
            <p style={{ color: '#9ca3af', fontSize: 14 }}>Exchanging OAuth token with the server.</p>
          </>
        )}

        {stage === 'success' && (
          <>
            <h2 style={{ color: '#fff', fontSize: 18, fontWeight: 600, marginBottom: 6 }}>GitHub Connected!</h2>
            <p style={{ color: '#9ca3af', fontSize: 14, marginBottom: 8 }}>{message}</p>
            <p style={{ color: '#6b7280', fontSize: 12 }}>Redirecting to Integrations...</p>
          </>
        )}

        {stage === 'error' && (
          <>
            <h2 style={{ color: '#fff', fontSize: 18, fontWeight: 600, marginBottom: 6 }}>Connection Failed</h2>
            <p style={{ color: '#f87171', fontSize: 14, marginBottom: 8 }}>{message}</p>
            <p style={{ color: '#6b7280', fontSize: 12 }}>Redirecting you back...</p>
          </>
        )}
      </div>
    </div>
  );
};
