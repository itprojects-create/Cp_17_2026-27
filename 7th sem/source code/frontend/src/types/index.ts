export interface EmployeeProfile {
  name: string;
  email: string;
  employee_id?: string;
  role: string;
  experience_level: string;
  tech_stack: string[];
  team?: string;
  manager?: string;
  mentor?: string;
  start_date?: string;
  skills?: string[];
  programming_languages?: string[];
  years_of_experience?: number;
  current_projects?: string[];
  past_experience?: string;
  github_username?: string;
  preferred_tools?: string[];
  timezone?: string;
}

export interface ChecklistItemType {
  id: string;
  task: string;
  category: string;
  owner: string;
  deadline: string;
  status: 'Not Started' | 'Pending' | 'In Progress' | 'Pending Verification' | 'Self-Reported Complete' | 'Completed' | 'Blocked' | 'Skipped';
  completion_evidence?: string;
  completion_source?: string;
  completed_at?: string;
  session_id?: string;
  description?: string;
  due_date?: string;
}

export interface OnboardingSession {
  session_id: string;
  employee_email: string;
  persona_match: string;
  status: string;
  started_at: string;
  completed_at?: string;
  current_phase: string;
  employee_name?: string;
  employee_role?: string | null;
  /** Verified completion percentage (tasks with evidence), computed by the backend. */
  progress?: number;
  completed_tasks?: number;
  total_tasks?: number;
  last_activity_at?: string | null;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  /** `notice`: an app message (e.g. the AI provider failed), not something the assistant said. */
  role: 'user' | 'assistant' | 'system' | 'notice';
  content: string;
  timestamp?: string;
  metadata?: Record<string, unknown>;
}

export interface ProgressData {
  total: number;
  completed: number;
  percentage: number;
  by_category?: Record<string, { total: number; completed: number }>;
}

export interface ActivityEvent {
  id: string;
  title: string;
  description: string;
  timestamp: string;
  type: 'milestone' | 'task' | 'system' | 'chat';
  icon?: string;
}

export interface AgentActivityItem {
  id: string;
  type: 'persona_identified' | 'kb_search' | 'kb_retrieved' | 'plan_generated' | 'checklist_update' | 'ticket_created' | 'hr_report' | 'intent_classification' | 'system' | string;
  label: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  details?: string;
  timestamp?: string;
}


export interface IntegrationItem {
  id: string;
  name: string;
  description: string;
  icon: string;
  status: 'connected' | 'disconnected' | 'pending' | 'not_configured' | 'misconfigured' | 'unavailable' | 'connection_failed';
  lastSync?: string;
}

export interface KnowledgeArticle {
  id: string;
  title: string;
  content: string;
  category: string;
  tags: string[];
  updated_at: string;
  /** Username of the HR admin who last edited the article; absent for the original documents. */
  updated_by?: string | null;
}

export interface PendingInvite {
  user_id: number;
  username: string;
  email: string;
  invited_by: string | null;
  invited_at: string;
  expires_at: string | null;
  status: 'pending' | 'expired';
}

export interface EmployeeChecklistItem {
  id: string;
  title: string;
  description: string;
  status: string;
  category: string;
  owner: string;
  deadline: string;
  completion_evidence: string | null;
  completed_at: string | null;
  completion_source: string | null;
}

export interface EmployeeDetail {
  employee: {
    user_id: number | null;
    username: string | null;
    email: string | null;
    name: string | null;
    role: string | null;
    years_of_experience: number | null;
    programming_languages: string[];
    tech_stack: string[];
    joined_at: string | null;
    invited_by: string | null;
    account_status: 'active' | 'invite_pending' | 'unknown';
  };
  session: {
    session_id: string;
    status: string | null;
    current_phase: string | null;
    persona_match: string | null;
    started_at: string | null;
    completed_at: string | null;
    last_activity_at: string | null;
  };
  progress: {
    total: number;
    completed: number;
    pending: number;
    skipped: number;
    blocked: number;
    pending_verification: number;
    percentage: number;
  };
  checklist: EmployeeChecklistItem[];
  starter_ticket: { reference: string | null; assigned_at: string | null } | null;
  activity: AgentActivityItem[];
}

export interface KnowledgeArticleInput {
  title: string;
  content: string;
  category: string;
}

export interface AnalyticsData {
  averageOnboardingTime: number;
  completionRate: number;
  activeOnboardings: number;
  blockedTasks: number;
  weeklyCompletions: number[];
  departmentBreakdown: Record<string, number>;
}

export interface User {
  id: number;
  username: string;
  email: string;
  role: 'employee' | 'hr_admin' | string;
  /** Employees must complete their profile before the rest of the app unlocks. */
  profile_completed?: boolean;
}

export interface RegisterPayload {
  username: string;
  email: string;
  password: string;
  role?: string;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface CreateSessionPayload {
  session_id?: string;
  persona_match?: string;
  employee_email?: string;
}

export interface UpdateChecklistPayload {
  status: 'Not Started' | 'In Progress' | 'Completed' | 'Blocked' | 'Skipped';
  task?: string;
  category?: string;
  deadline?: string;
}
