import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, User, Bot, Loader2, Plus, Trash2, MessageSquare, ChevronLeft, ChevronRight, XCircle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { ChatMessage, ChatSession } from '../types';

interface ChatProps {
  session: ChatSession;
  sessions: ChatSession[];
  onMessagesChange: (messages: ChatMessage[]) => void;
  onSessionChange: (sessionId: string) => void;
  onNewSession: () => void;
  onDeleteSession: (sessionId: string) => void;
  onClearAllSessions: () => void;
}

export default function Chat({
  session,
  sessions,
  onMessagesChange,
  onSessionChange,
  onNewSession,
  onDeleteSession,
  onClearAllSessions,
}: ChatProps) {
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sidebarExpanded, setSidebarExpanded] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const messages = session.messages;
  const selectedPerson = session.personContext;

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input on mount and session change
  useEffect(() => {
    inputRef.current?.focus();
  }, [session.id]);

  // Set initial welcome message when person context is set and no messages
  useEffect(() => {
    if (selectedPerson && messages.length === 0) {
      const welcomeMessage: ChatMessage = {
        id: 'welcome',
        role: 'assistant',
        content: `Hello! I'm TreePilot, your genealogy research assistant. I see you're interested in **${selectedPerson.fullName}**${selectedPerson.birthYear ? ` (born ${selectedPerson.birthYear})` : ''}.\n\nI can help you research this ancestor using:\n- 📖 Wikipedia for biographical information\n- 🔗 Wikidata for structured family data\n- 📰 Historical newspapers (1770-1963)\n- 📚 Google Books for genealogy resources\n\nWhat would you like to know about ${selectedPerson.firstName || 'this person'}?`,
        timestamp: new Date(),
      };
      onMessagesChange([welcomeMessage]);
    }
  }, [selectedPerson, messages.length, onMessagesChange]);

  const sendMessage = useCallback(async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    const newMessages = [...messages, userMessage];
    onMessagesChange(newMessages);
    setInput('');
    setIsLoading(true);

    // Create placeholder for assistant response
    const assistantMessageId = (Date.now() + 1).toString();
    const assistantMessage: ChatMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      thinking: '',
      toolStatus: '',
      timestamp: new Date(),
      isStreaming: true,
      isThinking: false,
    };
    onMessagesChange([...newMessages, assistantMessage]);

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: input.trim(),
          person_context: selectedPerson ? {
            fullName: selectedPerson.fullName,
            birthYear: selectedPerson.birthYear,
            deathYear: selectedPerson.deathYear,
            birthPlace: selectedPerson.birthPlace,
          } : null,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to send message');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response body');
      }

      let fullContent = '';
      let fullThinking = '';
      let currentToolStatus = '';
      let currentMessages = [...newMessages, assistantMessage];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              break;
            }
            try {
              const parsed = JSON.parse(data);
              
              if (parsed.type === 'thinking') {
                fullThinking += parsed.data;
                currentMessages = currentMessages.map(msg =>
                  msg.id === assistantMessageId
                    ? { ...msg, thinking: fullThinking, isThinking: true }
                    : msg
                );
                onMessagesChange(currentMessages);
              } else if (parsed.type === 'content') {
                fullContent += parsed.data;
                currentMessages = currentMessages.map(msg =>
                  msg.id === assistantMessageId
                    ? { ...msg, content: fullContent, isThinking: false }
                    : msg
                );
                onMessagesChange(currentMessages);
              } else if (parsed.type === 'tool_start') {
                currentToolStatus = `🔍 Searching ${parsed.data}...`;
                currentMessages = currentMessages.map(msg =>
                  msg.id === assistantMessageId
                    ? { ...msg, toolStatus: currentToolStatus }
                    : msg
                );
                onMessagesChange(currentMessages);
              } else if (parsed.type === 'tool_end') {
                currentToolStatus = '';
                currentMessages = currentMessages.map(msg =>
                  msg.id === assistantMessageId
                    ? { ...msg, toolStatus: '' }
                    : msg
                );
                onMessagesChange(currentMessages);
              } else if (parsed.content) {
                fullContent += parsed.content;
                currentMessages = currentMessages.map(msg =>
                  msg.id === assistantMessageId
                    ? { ...msg, content: fullContent }
                    : msg
                );
                onMessagesChange(currentMessages);
              }
            } catch {
              // Ignore parse errors for incomplete chunks
            }
          }
        }
      }

      // Mark as done streaming
      currentMessages = currentMessages.map(msg =>
        msg.id === assistantMessageId
          ? { ...msg, isStreaming: false }
          : msg
      );
      onMessagesChange(currentMessages);
    } catch (error) {
      console.error('Chat error:', error);
      const errorMessages = [...newMessages, {
        ...assistantMessage,
        content: 'Sorry, I encountered an error while researching. Please try again.',
        isStreaming: false,
      }];
      onMessagesChange(errorMessages);
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, selectedPerson, messages, onMessagesChange]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const suggestedQueries = selectedPerson
    ? [
        `What can you find about ${selectedPerson.fullName}?`,
        `Search for newspaper mentions of the ${selectedPerson.lastName} family`,
        `Find historical records from ${selectedPerson.birthPlace || 'their hometown'}`,
      ]
    : [
        'How do I start researching my family history?',
        'What are the best sources for genealogy research?',
        'Search for historical newspapers about immigration',
      ];

  return (
    <div className="flex h-full">
      {/* Session Sidebar */}
      <div
        className={`session-sidebar flex-shrink-0 bg-slate-800 border-r border-slate-700 flex flex-col transition-all duration-200 ${
          sidebarExpanded ? 'w-56' : 'w-12'
        }`}
      >
        {/* Sidebar Header */}
        <div className="p-2 border-b border-slate-700 flex items-center justify-between">
          {sidebarExpanded && (
            <span className="text-sm font-medium text-slate-300">Chats</span>
          )}
          <button
            onClick={() => setSidebarExpanded(!sidebarExpanded)}
            className="p-1.5 rounded hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
            title={sidebarExpanded ? 'Collapse' : 'Expand'}
          >
            {sidebarExpanded ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
        </div>

        {/* New Session Button */}
        <div className="p-2 border-b border-slate-700">
          <button
            onClick={onNewSession}
            className={`w-full flex items-center gap-2 p-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white transition-colors ${
              sidebarExpanded ? '' : 'justify-center'
            }`}
            title="New Chat"
          >
            <Plus className="w-4 h-4" />
            {sidebarExpanded && <span className="text-sm">New Chat</span>}
          </button>
        </div>

        {/* Session List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => onSessionChange(s.id)}
              className={`session-item w-full flex items-center gap-2 p-2 rounded-lg transition-colors group ${
                s.id === session.id
                  ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-600/50'
                  : 'text-slate-300 hover:bg-slate-700'
              } ${sidebarExpanded ? '' : 'justify-center'}`}
              title={s.name}
            >
              <MessageSquare className="w-4 h-4 flex-shrink-0" />
              {sidebarExpanded && (
                <>
                  <span className="flex-1 text-left text-sm truncate">{s.name}</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteSession(s.id);
                    }}
                    className="session-delete opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-600/20 text-slate-400 hover:text-red-400 transition-all"
                    title="Delete chat"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </>
              )}
            </button>
          ))}
        </div>

        {/* Clear All Button */}
        {sidebarExpanded && sessions.length > 1 && (
          <div className="p-2 border-t border-slate-700">
            <button
              onClick={onClearAllSessions}
              className="w-full flex items-center justify-center gap-2 p-2 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-600/10 transition-colors text-sm"
              title="Clear all chats"
            >
              <XCircle className="w-4 h-4" />
              Clear All
            </button>
          </div>
        )}
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Messages Container */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 ? (
            <div className="text-center py-8">
              <Bot className="w-12 h-12 mx-auto text-emerald-500 mb-3" />
              <h2 className="text-xl font-bold text-white mb-2">
                Start Your Research
              </h2>
              <p className="text-slate-400 mb-4 text-sm">
                Ask me anything about genealogy research
              </p>
              
              {/* Suggested Queries */}
              <div className="space-y-2 max-w-md mx-auto">
                {suggestedQueries.map((query, i) => (
                  <button
                    key={i}
                    onClick={() => setInput(query)}
                    className="w-full text-left p-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm transition-colors"
                  >
                    {query}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((message) => (
              <div
                key={message.id}
                className={`flex gap-3 ${
                  message.role === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
                {message.role === 'assistant' && (
                  <div className="w-7 h-7 rounded-full bg-emerald-600 flex items-center justify-center flex-shrink-0">
                    <Bot className="w-4 h-4 text-white" />
                  </div>
                )}
                
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                    message.role === 'user'
                      ? 'bg-emerald-600 text-white'
                      : 'bg-slate-800 text-slate-100'
                  }`}
                >
                  {message.role === 'assistant' ? (
                    <div className="message-content prose prose-invert prose-sm max-w-none">
                      {/* Thinking/Reasoning Section */}
                      {message.thinking && (
                        <details className="mb-3 border border-slate-600 rounded-lg overflow-hidden" open={message.isThinking}>
                          <summary className="px-3 py-2 bg-slate-700 cursor-pointer text-slate-300 text-sm font-medium flex items-center gap-2 hover:bg-slate-600 transition-colors">
                            <span className="text-purple-400">💭</span>
                            <span>Thinking...</span>
                            {message.isThinking && (
                              <span className="ml-auto inline-block w-2 h-2 bg-purple-400 rounded-full animate-pulse" />
                            )}
                          </summary>
                          <div className="px-3 py-2 bg-slate-900/50 text-slate-400 text-sm italic whitespace-pre-wrap max-h-48 overflow-y-auto">
                            {message.thinking}
                          </div>
                        </details>
                      )}
                      
                      {/* Tool Status */}
                      {message.toolStatus && (
                        <div className="mb-2 px-3 py-2 bg-slate-700 rounded-lg text-amber-400 text-sm flex items-center gap-2">
                          <Loader2 className="w-4 h-4 animate-spin" />
                          {message.toolStatus}
                        </div>
                      )}
                      
                      {/* Main Content */}
                      <ReactMarkdown>{message.content || (message.thinking ? '' : '...')}</ReactMarkdown>
                      {message.isStreaming && !message.isThinking && (
                        <span className="inline-block w-2 h-4 bg-emerald-500 animate-pulse ml-1" />
                      )}
                    </div>
                  ) : (
                    <p className="text-sm">{message.content}</p>
                  )}
                </div>

                {message.role === 'user' && (
                  <div className="w-7 h-7 rounded-full bg-slate-600 flex items-center justify-center flex-shrink-0">
                    <User className="w-4 h-4 text-white" />
                  </div>
                )}
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Selected Person Context */}
        {selectedPerson && (
          <div className="px-4 py-2 bg-slate-800/50 border-t border-slate-700">
            <div className="text-xs text-slate-400">
              Researching:{' '}
              <span className="text-emerald-400 font-medium">
                {selectedPerson.fullName}
              </span>
              {selectedPerson.birthYear && (
                <span className="ml-1">
                  ({selectedPerson.birthYear}
                  {selectedPerson.deathYear && ` - ${selectedPerson.deathYear}`})
                </span>
              )}
            </div>
          </div>
        )}

        {/* Input Area */}
        <div className="p-3 border-t border-slate-700">
          <div className="flex gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your ancestors..."
              rows={1}
              className="flex-1 bg-slate-800 text-white rounded-xl px-4 py-2.5 resize-none focus:outline-none focus:ring-2 focus:ring-emerald-500 placeholder-slate-400 text-sm"
              disabled={isLoading}
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim() || isLoading}
              className="bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-white rounded-xl px-4 py-2.5 transition-colors"
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
