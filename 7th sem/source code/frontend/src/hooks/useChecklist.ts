import { useState, useCallback } from 'react';
import type { ChecklistItemType, ProgressData } from '../types';
import { api } from '../services/api';
import toast from 'react-hot-toast';

export const useChecklist = (sessionId: string | null) => {
  const [checklist, setChecklist] = useState<ChecklistItemType[]>([]);
  const [progress, setProgress] = useState<ProgressData | null>(null);
  const [isChecklistLoading, setIsChecklistLoading] = useState(false);

  const patchChecklistItem = useCallback((itemId: string, status?: string, done?: boolean) => {
    let updatedChecklist: ChecklistItemType[] = [];
    setChecklist((prev) => {
      updatedChecklist = prev.map((item) => {
        if (item.id !== itemId) return item;
        if (status) return { ...item, status: status as ChecklistItemType['status'] };
        if (typeof done === 'boolean') {
          return { ...item, status: done ? 'Completed' : item.status };
        }
        return item;
      });
      return updatedChecklist;
    });

    setProgress((prev) => {
      if (!prev || updatedChecklist.length === 0) return prev;
      const completed = updatedChecklist.filter((i) => i.status === 'Completed').length;
      const total = updatedChecklist.length;
      return {
        ...prev,
        completed,
        total,
        percentage: total > 0 ? Math.round((completed / total) * 10000) / 100 : 0,
      };
    });
  }, []);

  const loadChecklist = useCallback(async () => {
    if (!sessionId) return;
    setIsChecklistLoading(true);
    try {
      const items = await api.getChecklist(sessionId);
      setChecklist(items);
      const prog = await api.getProgress(sessionId);
      setProgress(prog);
    } catch (error) {
      console.error("Error loading checklist", error);
    } finally {
      setIsChecklistLoading(false);
    }
  }, [sessionId]);

  const updateItem = async (itemId: string, status: string) => {
    if (!sessionId) return;
    try {
      await api.updateChecklistItem(
        sessionId,
        itemId,
        status,
        status === 'Completed' ? 'User confirmed completion from the onboarding checklist.' : undefined,
      );
      toast.success(`Task ${itemId} marked as ${status}`);
      await loadChecklist(); // Reload to get updated progress
    } catch (error) {
      console.error("Error updating checklist item", error);
    }
  };

  return { checklist, progress, isChecklistLoading, loadChecklist, updateItem, patchChecklistItem };
};
