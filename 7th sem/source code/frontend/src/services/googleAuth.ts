import { api } from './api';
import { getErrorDetail } from './errors';
import type { User } from '../types';
import toast from 'react-hot-toast';

export interface GoogleAuthCallbacks {
  onSuccess: (data: { access_token: string; token_type: string; user: User }) => void;
  onError?: (errorMessage: string) => void;
  onLoading?: (isLoading: boolean) => void;
}

/**
 * Triggers Google's native OAuth 2.0 popup / "Choose an account" screen.
 * Directly communicates with accounts.google.com and exchanges token with NovaByte backend.
 */
export async function launchGoogleOAuth({ onSuccess, onError, onLoading }: GoogleAuthCallbacks) {
  const clientId =
    (import.meta.env.VITE_GOOGLE_CLIENT_ID || localStorage.getItem('google_client_id') || '').trim();

  // If Client ID is missing, prompt user directly for their Google OAuth Client ID
  if (!clientId) {
    const input = window.prompt(
      'To launch the official Google Account Chooser screen, please provide your Google OAuth 2.0 Client ID (from Google Cloud Console):\n\nExample: 1234567890-abcdef.apps.googleusercontent.com'
    );
    if (input && input.trim()) {
      localStorage.setItem('google_client_id', input.trim());
      // Re-trigger with the newly saved client ID
      return launchGoogleOAuth({ onSuccess, onError, onLoading });
    } else {
      toast.error('Google Client ID is required to open the official Google OAuth screen.');
      onError?.('Google Client ID missing');
      return;
    }
  }

  // Ensure Google Identity Services SDK is loaded
  if (typeof window !== 'undefined' && window.google?.accounts?.oauth2) {
    onLoading?.(true);
    try {
      const client = window.google.accounts.oauth2.initTokenClient({
        client_id: clientId,
        scope: 'openid email profile',
        prompt: 'select_account',
        callback: async (tokenResponse) => {
          if (tokenResponse.error) {
            onLoading?.(false);
            const msg = tokenResponse.details || tokenResponse.error || 'Google Sign-In was cancelled or failed';
            toast.error(msg);
            onError?.(msg);
            return;
          }

          if (tokenResponse.access_token) {
            try {
              // 1. Fetch authenticated Google User Profile from Google's official userinfo API
              const res = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', {
                headers: { Authorization: `Bearer ${tokenResponse.access_token}` },
              });

              if (!res.ok) {
                throw new Error('Could not retrieve user info from Google');
              }

              const googleUser = await res.json();

              // 2. Authenticate & Provision session with NovaByte Backend
              const authData = await api.googleLogin({
                email: googleUser.email,
                name: googleUser.name || googleUser.given_name || 'Google Developer',
                picture: googleUser.picture,
              });

              onLoading?.(false);
              onSuccess(authData);
            } catch (err) {
              onLoading?.(false);
              const errMsg = getErrorDetail(
                err,
                (err instanceof Error && err.message) || 'Authentication with backend failed',
              );
              toast.error(errMsg);
              onError?.(errMsg);
            }
          }
        },
        error_callback: (nonOAuthError) => {
          onLoading?.(false);
          console.error('Google OAuth Non-OAuth Error:', nonOAuthError);
          toast.error('Could not open Google Sign-In popup. Check popup blockers or Client ID origin permissions.');
          onError?.('Popup blocked or origin mismatch');
        },
      });

      // Forces Google to always show the official "Choose an account" screen
      client.requestAccessToken({ prompt: 'select_account' });
    } catch (err) {
      onLoading?.(false);
      console.error('Failed to trigger Google OAuth popup:', err);
      toast.error('Failed to launch Google Sign-In screen.');
      onError?.(err instanceof Error ? err.message : String(err));
    }
  } else {
    // Fallback: Direct OAuth2 Popup Window to accounts.google.com
    onLoading?.(true);
    const redirectUri = window.location.origin;
    const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?client_id=${encodeURIComponent(
      clientId
    )}&redirect_uri=${encodeURIComponent(
      redirectUri
    )}&response_type=token&scope=openid%20email%20profile&prompt=select_account`;

    const width = 500;
    const height = 600;
    const left = window.screenX + (window.outerWidth - width) / 2;
    const top = window.screenY + (window.outerHeight - height) / 2;

    const popup = window.open(
      authUrl,
      'GoogleSignIn',
      `width=${width},height=${height},left=${left},top=${top},toolbar=0,scrollbars=1,status=1,resizable=1`
    );

    if (!popup) {
      onLoading?.(false);
      toast.error('Popup blocked by browser. Please allow popups for localhost.');
      onError?.('Popup blocked');
      return;
    }

    // Monitor popup window redirect
    const interval = setInterval(async () => {
      try {
        if (!popup || popup.closed) {
          clearInterval(interval);
          onLoading?.(false);
          return;
        }

        if (popup.location.href.includes(redirectUri) && popup.location.hash) {
          clearInterval(interval);
          const hash = popup.location.hash.substring(1);
          const params = new URLSearchParams(hash);
          const accessToken = params.get('access_token');
          popup.close();

          if (accessToken) {
            const res = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', {
              headers: { Authorization: `Bearer ${accessToken}` },
            });
            const googleUser = await res.json();
            const authData = await api.googleLogin({
              email: googleUser.email,
              name: googleUser.name,
              picture: googleUser.picture,
            });
            onLoading?.(false);
            onSuccess(authData);
          }
        }
      } catch {
        // Cross-origin access until redirect is expected
      }
    }, 500);
  }
}
