import { createContext, useContext } from 'react';

export interface User {
  id: number;
  username: string;
  email: string;
  role?: string;
  /** Employees must complete their profile before the rest of the app unlocks. */
  profile_completed?: boolean;
}

export interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (token: string, user: User) => void;
  logout: () => void;
  isAuthenticated: boolean;
  isAdmin: boolean;
  isLoading: boolean;
  /** Employee without a complete profile: only Profile and Settings are available. */
  needsProfile: boolean;
  /** Re-fetch the user (e.g. after the profile is completed). */
  refreshUser: () => Promise<void>;
}

// Pages an employee can open before their profile is complete.
export const PROFILE_GATE_ALLOWED = ['/app/profile', '/app/settings'];

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
