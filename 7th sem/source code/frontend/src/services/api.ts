import axios from 'axios';
import type { 
  ChatMessage, 
  ChecklistItemType, 
  KnowledgeArticle,
  KnowledgeArticleInput,
  EmployeeDetail,
  PendingInvite,
  OnboardingSession,
  User,
  RegisterPayload,
  LoginCredentials,
  CreateSessionPayload,
  ProgressData,
  AgentActivityItem,
  IntegrationItem
} from '../types';

import toast from 'react-hot-toast';

export interface KnowledgeCitation {
  source: string;
  article_id: string;
  section?: string | null;
  title?: string | null;
  score?: number;
}

/** `ai`: model-written answer; `excerpts`: model unavailable, raw passages; `none`: nothing relevant found. */
export interface KnowledgeAnswer {
  answer: string;
  citations: KnowledgeCitation[];
  mode: 'ai' | 'excerpts' | 'none';
}

export interface LLMProviderStatus {
  provider: string;
  model: string;
  status: 'active' | 'fallback' | 'unavailable' | string;
  error?: string | null;
  /** Live check result (only with `getLLMStatus(true)`). */
  health?: 'ok' | 'failing' | 'unavailable';
  health_error?: string | null;
}

/** The primary LLM, plus the provider that takes over calls it fails. */
export interface LLMStatus extends LLMProviderStatus {
  fallback?: LLMProviderStatus | null;
}

/** One server-sent event from the chat stream endpoint. */
interface StreamEvent {
  type: string;
  content?: string;
  error?: string;
  name?: string;
  count?: number;
  activity?: AgentActivityItem;
  item_id?: string;
  status?: string;
  done?: boolean;
}

const BASE_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');
const API_BASE_URL = `${BASE_URL}/api`;

/**
 * WebSockets can't carry an Authorization header, so the token is offered as a subprotocol
 * (sent in the Sec-WebSocket-Protocol header) instead of the URL, keeping it out of server logs.
 */
export const WS_AUTH_PROTOCOL = 'novabyte.bearer';
export const wsAuthProtocols = (token: string | null) => (token ? [WS_AUTH_PROTOCOL, token] : []);
const WS_TIMEOUT_MS = 5000;

const getToken = () => localStorage.getItem('auth_token') || '';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config;

    // Immediately clear session and redirect to login on auth expiry
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
      return Promise.reject(error);
    }

    // Set up retry logic (up to 3 times) for server-side errors
    if (!config || !config.retryCount) {
      if (config) config.retryCount = 0;
    }

    if (config && config.retryCount < 3 && (!error.response || error.response.status >= 500)) {
      config.retryCount += 1;
      const backoffDelay = Math.pow(2, config.retryCount) * 1000; // 2s, 4s, 8s
      console.log(`API Error. Retrying request... (${config.retryCount}/3) in ${backoffDelay}ms`);
      
      await new Promise(resolve => setTimeout(resolve, backoffDelay));
      return apiClient(config);
    }

    console.error('API Error:', error);
    const message = error.response?.data?.detail || error.message || 'An unexpected error occurred';
    toast.error(`Error: ${message}`);
    return Promise.reject(error);
  }
);

export const api = {
  // Auth
  register: async (userData: RegisterPayload): Promise<User> => {
    const response = await apiClient.post('/auth/register', userData);
    return response.data;
  },
  login: async (credentials: LoginCredentials): Promise<{ access_token: string; token_type: string; user: User }> => {
    const formData = new URLSearchParams();
    formData.append('username', credentials.username);
    formData.append('password', credentials.password);
    const response = await apiClient.post('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });
    return response.data;
  },
  googleLogin: async (payload: { credential?: string; email?: string; name?: string; picture?: string }): Promise<{ access_token: string; token_type: string; user: User }> => {
    const response = await apiClient.post('/auth/google', payload);
    return response.data;
  },
  githubLogin: async (payload: { username?: string; email?: string; name?: string }): Promise<{ access_token: string; token_type: string; user: User }> => {
    const response = await apiClient.post('/auth/github', payload);
    return response.data;
  },
  getMe: async (): Promise<User> => {
    const response = await apiClient.get('/auth/me');
    return response.data;
  },

  logout: async () => {
    const response = await apiClient.post('/auth/logout');
    return response.data;
  },
  requestPasswordReset: async (email: string) => {
    const response = await apiClient.post('/auth/forgot-password/request', { email });
    return response.data as { message: string };
  },
  inviteEmployee: async (payload: { username: string; email: string }) => {
    const response = await apiClient.post('/auth/invite', payload);
    return response.data as { user: User; session_id: string; email_sent: boolean };
  },
  getPendingInvites: async () => {
    const response = await apiClient.get('/auth/invites');
    return response.data.invites as PendingInvite[];
  },
  resendInvite: async (userId: number) => {
    const response = await apiClient.post(`/auth/invites/${userId}/resend`);
    return response.data as PendingInvite & { email_sent: boolean };
  },
  cancelInvite: async (userId: number) => {
    await apiClient.delete(`/auth/invites/${userId}`);
  },
  getEmployeeDetail: async (sessionId: string) => {
    const response = await apiClient.get(`/dashboard/employees/${encodeURIComponent(sessionId)}`);
    return response.data as EmployeeDetail;
  },
  resetPassword: async (token: string, newPassword: string) => {
    const response = await apiClient.post('/auth/forgot-password/reset', {
      token,
      new_password: newPassword,
    });
    return response.data as { message: string };
  },

  // Session
  createSession: async (data: CreateSessionPayload | Partial<OnboardingSession>): Promise<OnboardingSession> => {
    const response = await apiClient.post('/sessions', data);
    return response.data;
  },

  getSessions: async () => {
    const response = await apiClient.get('/sessions');
    return response.data.sessions;
  },
  getSession: async (sessionId: string) => {
    const response = await apiClient.get(`/sessions/${sessionId}`);
    return response.data;
  },
  completeSession: async (sessionId: string) => {
    const response = await apiClient.post(`/sessions/${sessionId}/complete`);
    return response.data;
  },

  // Chat
  getChatHistory: async (sessionId: string) => {
    const response = await apiClient.get(`/sessions/${sessionId}/chat`);
    return response.data.messages as ChatMessage[];
  },
  getActivity: async (sessionId: string) => {
    const response = await apiClient.get(`/sessions/${sessionId}/activity`);
    return response.data.activities as AgentActivityItem[];
  },
  sendMessage: async (sessionId: string, message: { content: string, id?: string }) => {
    const response = await apiClient.post(`/sessions/${sessionId}/chat`, message);
    return response.data as ChatMessage;
  },
  sendMessageStream: async (
    sessionId: string, 
    content: string, 
    onChunk: (chunk: string) => void,
    onToolCall: (toolName: string) => void,
    onToolResult: (count: number) => void,
    onChecklistItemUpdated?: (payload: { item_id: string; status?: string; done?: boolean }) => void,
    onActivity?: (activity: AgentActivityItem) => void,
    onNotice?: (content: string) => void
  ) => {
    const token = getToken();

    const handleEvent = (data: StreamEvent) => {
      if (data.type === 'chunk') {
        onChunk(data.content ?? '');
      } else if (data.type === 'activity' && onActivity && data.activity) {
        onActivity(data.activity);
      } else if (data.type === 'tool_call') {
        onToolCall(data.name ?? '');
      } else if (data.type === 'tool_result') {
        onToolResult(data.count ?? 0);
      } else if (data.type === 'checklist_item_updated' && data.item_id && onChecklistItemUpdated) {
        onChecklistItemUpdated({ item_id: data.item_id, status: data.status, done: data.done });
      } else if (data.type === 'checklist_updated' && data.item_id && onChecklistItemUpdated) {
        // Backward compatibility with older event names.
        onChecklistItemUpdated({ item_id: data.item_id, status: data.status, done: data.status === 'Completed' });
      } else if (data.type === 'notice') {
        onNotice?.(data.content ?? '');
      } else if (data.type === 'error') {
        throw new Error(data.content || data.error || 'Streaming error');
      }
    };


    const streamViaSSE = async () => {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) headers.Authorization = `Bearer ${token}`;

      const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/chat/stream`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ content }),
      });

      if (!response.body) throw new Error('No response body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(trimmed.slice(6));
            handleEvent(data);
          } catch (e) {
            console.error('Error parsing stream data', e, trimmed);
          }
        }
      }

      const last = buffer.trim();
      if (last.startsWith('data: ')) {
        const data = JSON.parse(last.slice(6));
        handleEvent(data);
      }
    };

    const streamViaWebSocket = async () => {
      const wsBase = API_BASE_URL.replace(/^http/i, 'ws').replace(/\/api$/, '');
      const wsUrl = `${wsBase}/api/ws/chat/${sessionId}`;

      return new Promise<void>((resolve, reject) => {
        let settled = false;
        const ws = new WebSocket(wsUrl, wsAuthProtocols(getToken()));

        const fail = (error: Error) => {
          if (settled) return;
          settled = true;
          try { ws.close(); } catch {
            // no-op
          }
          reject(error);
        };

        ws.onopen = () => {
          try {
            ws.send(JSON.stringify({ message: content }));
          } catch {
            fail(new Error('Failed to send WebSocket message'));
          }
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            handleEvent(data);
            if (data.type === 'done') {
              if (!settled) {
                settled = true;
                ws.close();
                resolve();
              }
            }
          } catch {
            fail(new Error('Invalid WebSocket payload'));
          }
        };

        ws.onerror = () => {
          fail(new Error('WebSocket connection failed'));
        };

        ws.onclose = () => {
          if (!settled) {
            settled = true;
            resolve();
          }
        };

        setTimeout(() => {
          if (!settled && ws.readyState !== WebSocket.OPEN) {
            fail(new Error('WebSocket connection timeout'));
          }
        }, WS_TIMEOUT_MS);
      });
    };

    if (token) {
      try {
        await streamViaWebSocket();
        return;
      } catch (error) {
        console.warn('WebSocket stream failed, falling back to SSE', error);
      }
    }

    await streamViaSSE();
  },

  // Checklist
  getChecklist: async (sessionId: string) => {
    const response = await apiClient.get(`/sessions/${sessionId}/checklist`);
    return response.data.checklist as ChecklistItemType[];
  },
  updateChecklistItem: async (sessionId: string, itemId: string, status: string, completionEvidence?: string) => {
    const response = await apiClient.patch(`/sessions/${sessionId}/checklist/${itemId}`, {
      status,
      ...(completionEvidence ? { completion_evidence: completionEvidence, completion_source: 'user_confirmation' } : {}),
    });
    return response.data;
  },

  // Progress
  getProgress: async (sessionId: string) => {
    const response = await apiClient.get(`/sessions/${sessionId}/progress`);
    return response.data;
  },

  // Knowledge Base
  getKnowledgeArticles: async (params?: { q?: string; category?: string }) => {
    const response = await apiClient.get('/knowledge/articles', { params });
    return response.data.articles as KnowledgeArticle[];
  },
  getKnowledgeArticle: async (articleId: string) => {
    const response = await apiClient.get(`/knowledge/articles/${articleId}`);
    return response.data as KnowledgeArticle;
  },
  // HR admin only. `indexed` is false when the document saved but search indexing failed.
  createKnowledgeArticle: async (article: KnowledgeArticleInput) => {
    const response = await apiClient.post('/knowledge/articles', article);
    return response.data as KnowledgeArticle & { indexed: boolean };
  },
  updateKnowledgeArticle: async (articleId: string, article: KnowledgeArticleInput) => {
    const response = await apiClient.put(`/knowledge/articles/${encodeURIComponent(articleId)}`, article);
    return response.data as KnowledgeArticle & { indexed: boolean };
  },
  deleteKnowledgeArticle: async (articleId: string) => {
    await apiClient.delete(`/knowledge/articles/${encodeURIComponent(articleId)}`);
  },
  askKnowledge: async (query: string) => {
    const response = await apiClient.post('/knowledge/ask', { query });
    return response.data as KnowledgeAnswer;
  },

  // Settings
  getSettings: async () => {
    const response = await apiClient.get('/settings');
    return response.data as {
      emailNotifications: boolean;
      checklistReminders: boolean;
      securityAlerts: boolean;
      weeklyDigest: boolean;
      autoStartLastSession: boolean;
      compactSidebar: boolean;
      timezone: string;
    };
  },
  updateSettings: async (settings: {
    emailNotifications: boolean;
    checklistReminders: boolean;
    securityAlerts: boolean;
    weeklyDigest: boolean;
    autoStartLastSession: boolean;
    compactSidebar: boolean;
    timezone: string;
  }) => {
    const response = await apiClient.put('/settings', settings);
    return response.data as {
      emailNotifications: boolean;
      checklistReminders: boolean;
      securityAlerts: boolean;
      weeklyDigest: boolean;
      autoStartLastSession: boolean;
      compactSidebar: boolean;
      timezone: string;
    };
  },

  // Profile
  getProfile: async () => {
    const response = await apiClient.get('/profile');
    return response.data as {
      name: string;
      email: string;
      role: string;
      skills: string[];
      programming_languages: string[];
      tech_stack: string[];
      years_of_experience: number;
      current_projects: string;
      past_experience: string;
      github_username: string;
      preferred_tools: string[];
      timezone: string;
    };
  },
  getProfileOptions: async () => {
    const response = await apiClient.get('/profile/options');
    return response.data as {
      roles: string[];
      languages: string[];
      skills: string[];
      tools: string[];
      timezones: string[];
    };
  },
  updateProfile: async (profile: {
    name: string;
    email: string;
    role: string;
    skills: string[];
    programming_languages: string[];
    tech_stack: string[];
    years_of_experience: number;
    current_projects: string;
    past_experience: string;
    github_username: string;
    preferred_tools: string[];
    timezone: string;
  }) => {
    const response = await apiClient.put('/profile', profile);
    return response.data as typeof profile & { profile_completed: boolean; missing_fields: string[] };
  },

  // Dashboard meta data
  getTimeline: async () => {
    const response = await apiClient.get('/dashboard/timeline');
    return response.data as { events: Array<{ id: string; title: string; description: string; date: string; completed: boolean; kind: string }>; progress?: ProgressData };
  },
  getRoadmap: async () => {
    const response = await apiClient.get('/dashboard/roadmap');
    return response.data as { steps: Array<{ id: string; title: string; description: string; tasks: string[]; status: 'completed' | 'active' | 'locked'; duration: string }>; progress?: ProgressData; session_status?: string; current_phase?: string };
  },
  getAnalytics: async () => {
    const response = await apiClient.get('/dashboard/analytics');
    return response.data as {
      averageOnboardingTime: number | null;
      medianOnboardingTime: number | null;
      totalSessions: number;
      completedOnboardings: number;
      completionRate: number;
      activeOnboardings: number;
      blockedTasks: number;
      pendingVerificationTasks: number;
      weeklyCompletions: Array<{ week: string; completions: number }>;
      departmentBreakdown: Array<{ name: string; count: number; color?: string }>;
      insights: Array<{ label: string; value: string; trend: string | null }>;
      phaseBreakdown: Array<{ phase: string; count: number; pct: number }>;
      definitions: Record<string, string>;
    };
  },
  getIntegrations: async () => {
    const response = await apiClient.get('/dashboard/integrations');
    return response.data as {
      integrations: Array<{
        id: string;
        name: string;
        description: string;
        status: IntegrationItem['status'];
        mode: 'mock' | 'real' | string;
        lastSync?: string;
        color: string;
      }>;
    };
  },
  connectIntegration: async (integrationId: string) => {
    const response = await apiClient.post(`/dashboard/integrations/${integrationId}/connect`);
    return response.data;
  },
  syncIntegrations: async () => {
    const response = await apiClient.post('/dashboard/integrations/sync');
    return response.data;
  },
  /** With `check`, the backend sends each configured model a tiny request and reports `health`. */
  getLLMStatus: async (check = false) => {
    const response = await apiClient.get('/system/llm-status', { params: check ? { check: true } : undefined });
    return response.data as LLMStatus;
  },

  // GitHub OAuth & Data
  getGitHubOAuthUrl: async (): Promise<{ auth_url: string }> => {
    const response = await apiClient.get('/github/oauth/redirect');
    return response.data;
  },
  handleGitHubOAuthCallback: async (code: string, state: string): Promise<{
    ok: boolean;
    status: string;
    github_username: string;
    github_name: string;
    github_avatar: string;
    lastSync: string;
  }> => {
    const response = await apiClient.post('/github/oauth/callback', { code, state });
    return response.data;
  },
  getGitHubStatus: async (): Promise<{
    connected: boolean;
    status: string;
    lastSync?: string;
  }> => {
    const response = await apiClient.get('/github/status');
    return response.data;
  },
  getGitHubData: async (): Promise<{
    user: {
      login: string;
      name: string;
      avatar_url: string;
      html_url: string;
      public_repos: number;
      followers: number;
      following: number;
      bio?: string;
    } | null;
    repos: Array<{
      id: number;
      name: string;
      full_name: string;
      description?: string;
      html_url: string;
      language?: string;
      stargazers_count: number;
      forks_count: number;
      open_issues_count: number;
      updated_at: string;
      private: boolean;
      visibility: string;
    }>;
    issues: Array<{
      id: number;
      number: number;
      title: string;
      html_url: string;
      state: string;
      created_at: string;
      updated_at: string;
      repo: string;
      labels: string[];
      comments: number;
    }>;
    pull_requests: Array<{
      id: number;
      number: number;
      title: string;
      html_url: string;
      state: string;
      created_at: string;
      updated_at: string;
      repo: string;
      labels: string[];
    }>;
  }> => {
    const response = await apiClient.get('/github/data');
    return response.data;
  },
  disconnectGitHub: async (): Promise<{ ok: boolean; status: string }> => {
    const response = await apiClient.post('/github/disconnect');
    return response.data;
  },
};
