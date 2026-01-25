import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, User, Bot, Loader2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Individual, ChatMessage } from '../types';

interface ChatProps {
  selectedPerson: Individual | null;
}

export default function Chat({ selectedPerson }: ChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Set initial message when person is selected
  useEffect(() => {
    if (selectedPerson && messages.length === 0) {
      const welcomeMessage: ChatMessage = {
        id: 'welcome',
        role: 'assistant',
        content: `Hello! I'm TreePilot, your genealogy research assistant. I see you're interested in **${selectedPerson.fullName}**${selectedPerson.birthYear ? ` (born ${selectedPerson.birthYear})` : ''}.\n\nI can help you research this ancestor using:\n- 📖 Wikipedia for biographical information\n- 🔗 Wikidata for structured family data\n- 📰 Historical newspapers (1770-1963)\n- 📚 Google Books for genealogy resources\n\nWhat would you like to know about ${selectedPerson.firstName || 'this person'}?`,
        timestamp: new Date(),
      };
      setMessages([welcomeMessage]);
    }
  }, [selectedPerson]);

  const sendMessage = useCallback(async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    // Create placeholder for assistant response
    const assistantMessageId = (Date.now() + 1).toString();
    const assistantMessage: ChatMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isStreaming: true,
    };
    setMessages(prev => [...prev, assistantMessage]);

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
              if (parsed.content) {
                fullContent += parsed.content;
                setMessages(prev =>
                  prev.map(msg =>
                    msg.id === assistantMessageId
                      ? { ...msg, content: fullContent }
                      : msg
                  )
                );
              }
            } catch {
              // Ignore parse errors for incomplete chunks
            }
          }
        }
      }

      // Mark as done streaming
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMessageId
            ? { ...msg, isStreaming: false }
            : msg
        )
      );
    } catch (error) {
      console.error('Chat error:', error);
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMessageId
            ? {
                ...msg,
                content: 'Sorry, I encountered an error while researching. Please try again.',
                isStreaming: false,
              }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, selectedPerson]);

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
        `Look for books about genealogy in this region`,
      ]
    : [
        'How do I start researching my family history?',
        'What are the best sources for genealogy research?',
        'Search for historical newspapers about immigration',
        'Find genealogy guides for beginners',
      ];

  return (
    <div className="flex flex-col h-full">
      {/* Messages Container */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="text-center py-12">
            <Bot className="w-16 h-16 mx-auto text-emerald-500 mb-4" />
            <h2 className="text-2xl font-bold text-white mb-2">
              Start Your Research
            </h2>
            <p className="text-slate-400 mb-6">
              Ask me anything about genealogy research, or select a person from your family tree
            </p>
            
            {/* Suggested Queries */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-w-2xl mx-auto">
              {suggestedQueries.map((query, i) => (
                <button
                  key={i}
                  onClick={() => setInput(query)}
                  className="text-left p-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm transition-colors"
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
                <div className="w-8 h-8 rounded-full bg-emerald-600 flex items-center justify-center flex-shrink-0">
                  <Bot className="w-5 h-5 text-white" />
                </div>
              )}
              
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                  message.role === 'user'
                    ? 'bg-emerald-600 text-white'
                    : 'bg-slate-800 text-slate-100'
                }`}
              >
                {message.role === 'assistant' ? (
                  <div className="message-content prose prose-invert prose-sm max-w-none">
                    <ReactMarkdown>{message.content || '...'}</ReactMarkdown>
                    {message.isStreaming && (
                      <span className="inline-block w-2 h-4 bg-emerald-500 animate-pulse ml-1" />
                    )}
                  </div>
                ) : (
                  <p>{message.content}</p>
                )}
              </div>

              {message.role === 'user' && (
                <div className="w-8 h-8 rounded-full bg-slate-600 flex items-center justify-center flex-shrink-0">
                  <User className="w-5 h-5 text-white" />
                </div>
              )}
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Selected Person Context */}
      {selectedPerson && (
        <div className="px-4 py-2 bg-slate-800 border-t border-slate-700">
          <div className="text-sm text-slate-400">
            Researching:{' '}
            <span className="text-emerald-400 font-medium">
              {selectedPerson.fullName}
            </span>
            {selectedPerson.birthYear && (
              <span className="ml-2">
                ({selectedPerson.birthYear}
                {selectedPerson.deathYear && ` - ${selectedPerson.deathYear}`})
              </span>
            )}
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className="p-4 border-t border-slate-700">
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your ancestors or genealogy research..."
            rows={1}
            className="flex-1 bg-slate-800 text-white rounded-xl px-4 py-3 resize-none focus:outline-none focus:ring-2 focus:ring-emerald-500 placeholder-slate-400"
            disabled={isLoading}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || isLoading}
            className="bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-white rounded-xl px-4 py-3 transition-colors"
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>
        <p className="text-xs text-slate-500 mt-2 text-center">
          TreePilot searches Wikipedia, Wikidata, historical newspapers, and Google Books
        </p>
      </div>
    </div>
  );
}
