import React, { useState } from 'react';
import type { ChatMessage } from '../../types';

type ChatWindowProps = {
  messages: ChatMessage[];
  isLoading: boolean;
  onSendMessage: (content: string) => Promise<void>;
  sessionStatus?: string;
};

export const ChatWindow: React.FC<ChatWindowProps> = ({
  messages,
  isLoading,
  onSendMessage,
  sessionStatus,
}) => {
  const [input, setInput] = useState('');

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const content = input.trim();
    if (!content || isLoading) {
      return;
    }
    setInput('');
    await onSendMessage(content);
  };

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="border-b border-gray-200 px-4 py-3">
        <p className="text-sm font-medium text-gray-700">Onboarding Assistant</p>
        {sessionStatus ? (
          <p className="text-xs text-gray-500">Session status: {sessionStatus}</p>
        ) : null}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-3">
          {messages.length === 0 ? (
            <div className="rounded-lg border border-dashed border-gray-300 p-4 text-sm text-gray-500">
              Start by introducing your role and stack.
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                className={
                  msg.role === 'user'
                    ? 'self-end rounded-lg bg-blue-600 px-4 py-2 text-sm text-white'
                    : 'self-start rounded-lg border border-gray-200 bg-gray-50 px-4 py-2 text-sm text-gray-800'
                }
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
            ))
          )}
          {isLoading ? (
            <div className="self-start rounded-lg border border-gray-200 bg-gray-50 px-4 py-2 text-sm text-gray-600">
              Assistant is typing...
            </div>
          ) : null}
        </div>
      </div>

      <form onSubmit={onSubmit} className="border-t border-gray-200 p-4">
        <div className="mx-auto flex w-full max-w-3xl gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about setup, checklist, or policies"
            className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm outline-none focus:border-blue-500"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-blue-300"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
};
