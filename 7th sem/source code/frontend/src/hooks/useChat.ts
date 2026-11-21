import { useState, useCallback, useEffect } from 'react';
import type { ChatMessage } from '../types';
import { api } from '../services/api';

export const useChat = (sessionId: string | null) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const loadHistory = useCallback(async () => {
    if (!sessionId) return;
    setIsLoading(true);
    try {
      const msgs = await api.getChatHistory(sessionId);
      
      // Sort messages by timestamp if needed, robustly handling missing timestamps
      msgs.sort((a, b) => new Date(a.timestamp || 0).getTime() - new Date(b.timestamp || 0).getTime());
      
      setMessages(msgs);
    } catch (error) {
      console.error('Failed to load history:', error);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const sendMessage = useCallback(async (content: string) => {
    if (!sessionId || !content.trim()) return;

    const userMsg: ChatMessage = {
      id: `user_${Date.now()}`,
      session_id: sessionId,
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const response = await api.sendMessage(sessionId, { 
        content,
        id: userMsg.id
      });
      setMessages((prev) => [...prev, response]);
    } catch (error) {
      console.error('Failed to send message:', error);
      // Fallback or error state handling could go here
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  return {
    messages,
    isLoading,
    sendMessage,
    setMessages
  };
};
