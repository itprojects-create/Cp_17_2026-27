import React, { useEffect, useRef, useState } from 'react';
import { Send, Bot, User, Sparkles, RotateCcw, Activity, PanelRightClose, PanelRightOpen, X, AlertTriangle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api } from '../services/api';
import type { ChatMessage, AgentActivityItem } from '../types';
import { AgentActivityPanel } from '../components/Chat/AgentActivityPanel';

export const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isInitializing, setIsInitializing] = useState(true);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionPhase, setSessionPhase] = useState<string>('collect_info');
  const [chatHistory, setChatHistory] = useState<{ id: string; title: string; date: string }[]>([]);
  const [activeTools, setActiveTools] = useState<string[]>([]);
  const [activities, setActivities] = useState<AgentActivityItem[]>([]);
  const [showActivityPanel, setShowActivityPanel] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(min-width: 1280px)').matches
  );
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const ensureSession = async (): Promise<string | null> => {
    if (sessionId) return sessionId;

    try {
      const created = await api.createSession({});
      const sid = created.session_id as string;
      setSessionId(sid);

      // Refresh sidebar history after creating the first session.
      const sessions = await api.getSessions();
      setChatHistory(
        sessions.map((s: { session_id: string; employee_email: string; started_at: string }) => ({
          id: s.session_id,
          title: s.employee_email,
          date: new Date(s.started_at).toLocaleDateString(),
        }))
      );

      return sid;
    } catch (e) {
      console.error(e);
      return null;
    }
  };

  useEffect(() => {
    const init = async () => {
      try {
        const sessions = await api.getSessions();
        if (sessions.length > 0) {
          const sid = sessions[0].session_id;
          setSessionId(sid);
          setSessionPhase(sessions[0].current_phase || 'onboarding');
          const history = await api.getChatHistory(sid);
          const persistedActivities = await api.getActivity(sid);
          setActivities(persistedActivities);
          history.sort((a: ChatMessage, b: ChatMessage) => new Date(a.timestamp || 0).getTime() - new Date(b.timestamp || 0).getTime());
          setMessages(history);
          setChatHistory(sessions.map((s: { session_id: string; employee_email: string; started_at: string }) => ({
            id: s.session_id,
            title: s.employee_email,
            date: new Date(s.started_at).toLocaleDateString(),
          })));
        } else {
          await ensureSession();
        }
      } catch (e) { console.error(e); }
      finally { setIsInitializing(false); }
    };
    
    init();
    // Run once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const activeSessionId = sessionId ?? await ensureSession();
    if (!activeSessionId) return;

    const content = input.trim();
    setInput('');
    const userMsgId = `user_${Date.now()}`;
    const userMsg: ChatMessage = {
      id: userMsgId, session_id: activeSessionId, role: 'user',
      content, timestamp: new Date().toISOString(),
    };
    
    // Add user message & placeholder AI message
    const aiMsgId = `ai_${Date.now()}`;
    const initialAiMsg: ChatMessage = {
      id: aiMsgId, session_id: activeSessionId, role: 'assistant',
      content: '', timestamp: new Date().toISOString(),
    };
    
    setMessages(prev => [...prev, userMsg, initialAiMsg]);
    setIsLoading(true);
    setActiveTools([]);

    try {
      await api.sendMessageStream(
        activeSessionId,
        content,
        (chunk) => {
          // Update the AI message chunk by chunk, replacing entirely as backend sends full buffer
          setMessages(prev => prev.map(m => m.id === aiMsgId ? { ...m, content: chunk } : m));
        },
        (toolName) => {
          setActiveTools(prev => [...prev, toolName]);
        },
        () => {
          // Keep tool badges visible briefly, then clear them once all results are processed
          setTimeout(() => setActiveTools([]), 2000);
        },
        undefined,
        (activity: AgentActivityItem) => {
          setActivities(prev => {
            const existingIndex = prev.findIndex(a => a.id === activity.id);
            if (existingIndex >= 0) {
              const updated = [...prev];
              updated[existingIndex] = activity;
              return updated;
            }
            return [...prev, activity];
          });
        },
        (notice) => {
          setMessages(prev => prev.map(m => m.id === aiMsgId ? { ...m, role: 'notice', content: notice } : m));
        }
      );
    } catch (e) { 
        console.error(e); 
        setMessages(prev => prev.map(m => m.id === aiMsgId ? { ...m, role: 'notice', content: 'Sorry, an error occurred while generating the response.' } : m));
    }
    finally { 
        setIsLoading(false); 
        setActiveTools([]);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const suggestions = [
    'What should I set up first?',
    'Show me the team structure',
    'How do I access the codebase?',
    'What are the coding standards?',
  ];

  return (
    <div className="flex h-full overflow-hidden">
      {/* Chat History Sidebar */}
      <div className="hidden lg:flex w-64 shrink-0 flex-col border-r border-(--border-default) bg-(--bg-secondary)">
        <div className="p-4 border-b border-(--border-default)">
          <h2 className="text-sm font-semibold text-(--text-primary)">Chat History</h2>
        </div>
        <div className="flex-1 overflow-y-auto scrollbar-thin p-2">
          {chatHistory.map(chat => (
            <button key={chat.id}
              onClick={() => setSessionId(chat.id)}
              className={`w-full text-left px-3 py-2.5 rounded-lg mb-1 transition-colors ${
                chat.id === sessionId
                  ? 'bg-primary-500/10 text-primary-500 font-medium'
                  : 'text-(--text-secondary) hover:bg-(--bg-tertiary)'
              }`}
            >
              <p className="text-sm font-medium truncate">{chat.title}</p>
              <p className="text-xs text-(--text-tertiary)">{chat.date}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Chat Main */}
      <div className="flex-1 flex flex-col min-w-0 h-full">
        {/* Top Control Bar */}
        <div className="h-12 border-b border-(--border-default) bg-(--bg-primary) px-4 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-semibold text-(--text-primary)">
              NovaByte Onboarding Agent
            </span>
          </div>
          <button
            onClick={() => setShowActivityPanel(prev => !prev)}
            aria-label={showActivityPanel ? 'Hide agent activity' : 'Show agent activity'}
            aria-expanded={showActivityPanel}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-colors cursor-pointer ${
              showActivityPanel
                ? 'bg-primary-500/10 text-primary-500 border-primary-500/30'
                : 'text-(--text-secondary) hover:text-(--text-primary) border-(--border-default)'
            }`}
            title={showActivityPanel ? "Hide Agent Activity" : "Show Agent Activity"}
          >
            <Activity size={13} />
            <span className="hidden sm:inline">Agent Activity</span>
            {showActivityPanel ? <PanelRightClose size={13} /> : <PanelRightOpen size={13} />}
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          {isInitializing ? (
            <div className="p-6 space-y-4 animate-pulse">
              {[70, 45, 85].map((w, i) => (
                <div key={i} className={`flex gap-3 ${i % 2 === 1 ? 'justify-end' : ''}`}>
                  {i % 2 === 0 && <div className="w-8 h-8 rounded-full bg-(--bg-tertiary) shrink-0" />}
                  <div className={`h-12 rounded-xl bg-(--bg-tertiary)`} style={{ width: `${w}%` }} />
                  {i % 2 === 1 && <div className="w-8 h-8 rounded-full bg-(--bg-tertiary) shrink-0" />}
                </div>
              ))}
            </div>
          ) : messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full p-8 animate-fade-in">
              <div className="w-16 h-16 rounded-2xl bg-linear-to-br from-primary-500/20 to-accent-500/20 flex items-center justify-center mb-4">
                <Sparkles size={28} className="text-primary-500" />
              </div>
              <h2 className="text-xl font-bold text-(--text-primary) mb-2">AI Onboarding Assistant</h2>
              <p className="text-(--text-secondary) text-sm text-center max-w-md mb-8">
                I'm here to guide you through your onboarding journey. Ask me anything about the company, your team, or your setup.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg">
                {suggestions.map(s => (
                  <button key={s} onClick={() => { setInput(s); inputRef.current?.focus(); }}
                    className="px-4 py-3 rounded-xl border border-(--border-default) text-sm text-(--text-secondary) hover:bg-(--bg-secondary) hover:border-primary-500/30 transition-all text-left">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto py-4 sm:py-6 px-3 sm:px-4 space-y-1">
              {messages.map((msg) => msg.role === 'notice' ? (
                <div key={msg.id} role="status" className="flex justify-center py-3 animate-fade-in">
                  <div className="flex items-start gap-2 max-w-[90%] px-3.5 py-2.5 rounded-xl border border-amber-500/25 bg-amber-500/8 text-xs text-amber-700 dark:text-amber-300">
                    <AlertTriangle size={14} className="shrink-0 mt-0.5" />
                    <span>{msg.content}</span>
                  </div>
                </div>
              ) : (
                <div key={msg.id} className={`flex gap-3 py-4 animate-fade-in ${msg.role === 'user' ? 'justify-end' : ''}`}>
                  {msg.role !== 'user' && (
                    <div className="w-8 h-8 rounded-lg bg-linear-to-br from-primary-500 to-accent-500 flex items-center justify-center shrink-0">
                      <Bot size={16} className="text-white" />
                    </div>
                  )}
                  <div className={`max-w-[85%] sm:max-w-[80%] min-w-0 rounded-2xl px-4 py-3 break-words ${
                    msg.role === 'user'
                      ? 'bg-primary-500 text-white rounded-br-md'
                      : 'bg-(--bg-secondary) text-(--text-primary) rounded-bl-md border border-(--border-default)'
                  }`}>
                    {msg.role === 'user' ? (
                      <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    ) : (
                      <div className="text-sm markdown-content">
                        {msg.content ? (
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                        ) : (
                          // If content is empty but it is the active streaming message
                          <div className="flex items-center gap-1.5 h-6">
                            <div className="w-2 h-2 bg-(--text-tertiary) rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                            <div className="w-2 h-2 bg-(--text-tertiary) rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                            <div className="w-2 h-2 bg-(--text-tertiary) rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                          </div>
                        )}
                      </div>
                    )}
                    {msg.timestamp && (
                      <p className={`text-[10px] mt-1.5 ${msg.role === 'user' ? 'text-white/60' : 'text-(--text-tertiary)'}`}>
                        {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </p>
                    )}
                  </div>
                  {msg.role === 'user' && (
                    <div className="w-8 h-8 rounded-lg bg-surface-600 flex items-center justify-center shrink-0">
                      <User size={16} className="text-white" />
                    </div>
                  )}
                </div>
              ))}
              {/* Tool Execution Badges */}
              {activeTools.length > 0 && (
                <div className="flex flex-col gap-2 py-2 pl-11 animate-fade-in">
                  {activeTools.map((tool, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs font-medium text-amber-500 bg-amber-500/10 px-3 py-1.5 rounded-full w-max">
                      <span className="animate-spin text-amber-500">⚙️</span>
                      {tool === 'get_checklist' && 'Checking your checklist...'}
                      {tool === 'update_checklist_item' && 'Updating task status...'}
                      {tool === 'get_progress' && 'Fetching progress data...'}
                      {tool === 'retrieve_knowledge' && 'Searching knowledge base...'}
                      {tool === 'generate_email_summary' && 'Preparing HR summary...'}
                      {![ 'get_checklist', 'update_checklist_item', 'get_progress', 'retrieve_knowledge', 'generate_email_summary'].includes(tool) && `Using tool: ${tool}...`}
                    </div>
                  ))}
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {/* Input Bar */}
        <div className="border-t border-(--border-default) p-3 sm:p-4 bg-(--bg-primary)">
          <div className="max-w-3xl mx-auto relative">
            <div className="flex items-end gap-2 p-2 rounded-2xl border border-(--border-default) bg-(--bg-secondary) focus-within:ring-2 focus-within:ring-primary-500/50 focus-within:border-primary-500/50 transition-all">
              <textarea
                ref={inputRef}
                id="chat-message-input"
                name="chatMessage"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type your message..."
                rows={1}
                className="flex-1 bg-transparent text-sm text-(--text-primary) placeholder:text-(--text-tertiary) focus:outline-none resize-none px-2 py-1.5 max-h-32"
                style={{ minHeight: '36px' }}
              />
              <div className="flex items-center gap-1 pb-1">
                <button
                  onClick={() => { setMessages([]); setActivities([]); }}
                  className="p-2 rounded-lg text-(--text-tertiary) hover:text-(--text-secondary) hover:bg-(--bg-tertiary) transition-colors cursor-pointer"
                  title="Clear chat"
                  aria-label="Clear chat"
                >
                  <RotateCcw size={16} />
                </button>
                <button
                  onClick={handleSend}
                  disabled={!input.trim() || isLoading}
                  className="p-2 rounded-lg bg-primary-500 text-white hover:bg-primary-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                  aria-label="Send message"
                >
                  <Send size={16} />
                </button>
              </div>
            </div>
            <p className="hidden sm:block text-xs text-(--text-tertiary) text-center mt-2">
              Autonomous AI onboarding assistant powered by LangGraph.
            </p>
          </div>
        </div>
      </div>

      {/* Real-Time Agent Activity Panel: inline on xl screens, slide-over below that */}
      {showActivityPanel && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/40 xl:hidden animate-fade-in"
            onClick={() => setShowActivityPanel(false)}
            aria-hidden="true"
          />
          <aside className="fixed inset-y-0 right-0 z-50 w-[min(20rem,90vw)] shadow-2xl animate-slide-right xl:static xl:z-auto xl:w-80 xl:shadow-none shrink-0 h-full">
            <button
              onClick={() => setShowActivityPanel(false)}
              className="xl:hidden absolute top-3 right-3 z-10 p-1.5 rounded-lg text-(--text-secondary) hover:bg-(--bg-tertiary) cursor-pointer"
              aria-label="Close agent activity"
            >
              <X size={16} />
            </button>
            <AgentActivityPanel
              activities={activities}
              isLoading={isLoading}
              activePhase={sessionPhase}
            />
          </aside>
        </>
      )}
    </div>
  );
};
