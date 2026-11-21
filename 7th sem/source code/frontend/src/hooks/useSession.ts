import { useState, useCallback } from 'react';
import type { OnboardingSession } from '../types';
import { api } from '../services/api';

export const useSession = () => {
  const [session, setSession] = useState<OnboardingSession | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const createSession = useCallback(async (data: Partial<OnboardingSession>) => {
    setIsLoading(true);
    try {
      const response = await api.createSession(data);
      const newSession = await api.getSession(response.session_id);
      setSession(newSession);
      return newSession;
    } catch (error) {
      console.error('Failed to create session:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadSession = useCallback(async (sessionId: string) => {
    setIsLoading(true);
    try {
      const data = await api.getSession(sessionId);
      setSession(data);
    } catch (error) {
      console.error('Failed to load session:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  return {
    session,
    isLoading,
    createSession,
    loadSession
  };
};
