import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useSession } from '../hooks/useSession';
import { useChat } from '../hooks/useChat';
import { useChecklist } from '../hooks/useChecklist';
import { ChatWindow } from '../components/Chat/ChatWindow';
import { ChecklistPanel } from '../components/Checklist/ChecklistPanel';
import { api } from '../services/api';
import toast from 'react-hot-toast';

export const OnboardingPage: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  
  const { session, loadSession } = useSession();
  const { messages, isLoading: isChatLoading, sendMessage } = useChat(sessionId || null);
  const { checklist, progress, isChecklistLoading, loadChecklist, updateItem } = useChecklist(sessionId || null);
  const [isCompleting, setIsCompleting] = useState(false);

  useEffect(() => {
    if (sessionId) {
      loadSession(sessionId);
      loadChecklist();
    }
  }, [sessionId, loadSession, loadChecklist]);

  const handleSendMessage = async (content: string) => {
    await sendMessage(content);
    if (sessionId) {
      // Small delay to allow backend to process persona match and checklist generation
      setTimeout(() => {
        loadSession(sessionId);
        loadChecklist();
      }, 500);
    }
  };

  const handleCompleteOnboarding = async () => {
    if (!sessionId) return;
    setIsCompleting(true);
    try {
      await api.completeSession(sessionId);
      toast.success("✨ Onboarding completed successfully! Welcome to NovaByte.");
      loadSession(sessionId);
    } catch (e) {
      console.error(e);
    } finally {
      setIsCompleting(false);
    }
  };

  if (!session) {
    return <div className="flex items-center justify-center h-screen">Loading session...</div>;
  }

  return (
    <div className="flex h-screen bg-white">
      {/* Sidebar Placeholder */}
      <div className="w-16 shrink-0 bg-blue-900 flex flex-col items-center py-4">
        {/* Logo or Home icon could go here */}
      </div>

      <div className="flex-1 flex flex-col h-full overflow-hidden relative">
        {/* Header Placeholder */}
        <header className="h-14 bg-white border-b border-gray-200 flex items-center px-6 justify-between shrink-0 z-10">
          <div className="font-semibold text-gray-800">
            {session.employee_email} Onboarding
          </div>
          <div className="flex items-center gap-3">
            {progress?.percentage === 100 && session.status !== 'Completed' && (
              <button 
                onClick={handleCompleteOnboarding}
                disabled={isCompleting}
                className="text-sm px-3 py-1.5 bg-green-600 text-white rounded-md font-medium hover:bg-green-700 transition"
              >
                {isCompleting ? 'Completing...' : 'Finish Onboarding'}
              </button>
            )}
            <div className="text-sm px-2 py-1 bg-blue-50 text-blue-700 rounded-md font-medium border border-blue-100">
              {session.status}
            </div>
          </div>
        </header>

        {/* Main Content Area */}
        <div className="flex-1 overflow-hidden flex relative">
          
          <main className="flex-1 h-full flex flex-col min-w-0">
            <ChatWindow 
              messages={messages} 
              isLoading={isChatLoading} 
              onSendMessage={handleSendMessage}
              sessionStatus={session.status}
            />
          </main>
          
          <aside className="hidden md:block h-full shadow-[-4px_0_15px_-3px_rgba(0,0,0,0.05)] relative z-20">
            <ChecklistPanel 
              checklist={checklist} 
              progress={progress} 
              isLoading={isChecklistLoading}
              onUpdateItem={updateItem}
            />
          </aside>
        </div>
      </div>
    </div>
  );
};
