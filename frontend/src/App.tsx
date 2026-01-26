import { useState, useCallback, useEffect, useRef } from 'react';
import { TreeDeciduous, Upload, Download, RefreshCw } from 'lucide-react';
import Chat from './components/Chat';
import GedcomImporter from './components/GedcomImporter';
import AncestorTree from './components/AncestorTree';
import ResizableDivider from './components/ResizableDivider';
import { Individual, TreeNode, ChatSession, ChatMessage } from './types';

const STORAGE_KEY_SESSIONS = 'treepilot-chat-sessions';
const STORAGE_KEY_ACTIVE_SESSION = 'treepilot-active-session';
const STORAGE_KEY_PANEL_WIDTH = 'treepilot-panel-width';

function createNewSession(personContext: Individual | null = null): ChatSession {
  return {
    id: crypto.randomUUID(),
    name: 'New Chat',
    messages: [],
    personContext,
    createdAt: Date.now(),
  };
}

function App() {
  const [individuals, setIndividuals] = useState<Individual[]>([]);
  const [selectedPerson, setSelectedPerson] = useState<Individual | null>(null);
  const [treeData, setTreeData] = useState<TreeNode | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [chatPanelWidth, setChatPanelWidth] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY_PANEL_WIDTH);
    return saved ? parseInt(saved, 10) : 450;
  });
  const containerRef = useRef<HTMLDivElement>(null);

  // Session management
  const [sessions, setSessions] = useState<ChatSession[]>(() => {
    const saved = localStorage.getItem(STORAGE_KEY_SESSIONS);
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        return [createNewSession()];
      }
    }
    return [createNewSession()];
  });

  const [activeSessionId, setActiveSessionId] = useState<string>(() => {
    const saved = localStorage.getItem(STORAGE_KEY_ACTIVE_SESSION);
    if (saved && sessions.find(s => s.id === saved)) {
      return saved;
    }
    return sessions[0]?.id || '';
  });

  // Persist sessions to localStorage
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY_SESSIONS, JSON.stringify(sessions));
  }, [sessions]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY_ACTIVE_SESSION, activeSessionId);
  }, [activeSessionId]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY_PANEL_WIDTH, chatPanelWidth.toString());
  }, [chatPanelWidth]);

  const activeSession = sessions.find(s => s.id === activeSessionId) || sessions[0];

  const handleGedcomLoaded = useCallback((loadedIndividuals: Individual[]) => {
    console.log('[TreePilot] GEDCOM loaded with', loadedIndividuals.length, 'individuals');
    setIndividuals(loadedIndividuals);
  }, []);

  const handlePersonSelect = useCallback(async (person: Individual) => {
    console.log('[TreePilot] Person selected:', person.fullName, 'ID:', person.id);
    setSelectedPerson(person);
    setIsLoading(true);

    // Update active session's person context
    setSessions(prev =>
      prev.map(s =>
        s.id === activeSessionId ? { ...s, personContext: person } : s
      )
    );

    try {
      const personId = person.id.replace(/@/g, '');
      const response = await fetch(`/api/tree/${personId}`);
      
      if (response.ok) {
        const data = await response.json();
        setTreeData(data.tree);
      }
    } catch (error) {
      console.error('[TreePilot] Failed to fetch tree:', error);
    } finally {
      setIsLoading(false);
    }
  }, [activeSessionId]);

  const handleResearchPerson = useCallback((person: Individual) => {
    setSelectedPerson(person);
    // Update active session's person context
    setSessions(prev =>
      prev.map(s =>
        s.id === activeSessionId ? { ...s, personContext: person } : s
      )
    );
  }, [activeSessionId]);

  // Session handlers
  const handleNewSession = useCallback(() => {
    const newSession = createNewSession(selectedPerson);
    setSessions(prev => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
  }, [selectedPerson]);

  const handleDeleteSession = useCallback((sessionId: string) => {
    setSessions(prev => {
      const filtered = prev.filter(s => s.id !== sessionId);
      // Ensure at least one session exists
      if (filtered.length === 0) {
        return [createNewSession(selectedPerson)];
      }
      return filtered;
    });
    // If deleting active session, switch to first available
    if (sessionId === activeSessionId) {
      setSessions(prev => {
        const remaining = prev.filter(s => s.id !== sessionId);
        if (remaining.length > 0) {
          setActiveSessionId(remaining[0].id);
        }
        return prev;
      });
    }
  }, [activeSessionId, selectedPerson]);

  const handleClearAllSessions = useCallback(() => {
    const newSession = createNewSession(selectedPerson);
    setSessions([newSession]);
    setActiveSessionId(newSession.id);
  }, [selectedPerson]);

  const handleSessionChange = useCallback((sessionId: string) => {
    setActiveSessionId(sessionId);
    // Restore person context from session
    const session = sessions.find(s => s.id === sessionId);
    if (session?.personContext) {
      setSelectedPerson(session.personContext);
    }
  }, [sessions]);

  const handleMessagesChange = useCallback((messages: ChatMessage[]) => {
    setSessions(prev =>
      prev.map(s => {
        if (s.id !== activeSessionId) return s;
        
        // Auto-name from first user message
        let name = s.name;
        if (s.name === 'New Chat' && messages.length > 0) {
          const firstUserMsg = messages.find(m => m.role === 'user');
          if (firstUserMsg) {
            name = firstUserMsg.content.slice(0, 30) + (firstUserMsg.content.length > 30 ? '...' : '');
          }
        }
        
        return { ...s, messages, name };
      })
    );
  }, [activeSessionId]);

  // Reload individuals and tree from backend (picks up any LLM modifications)
  const handleReloadTree = useCallback(async () => {
    console.log('[TreePilot] Reloading tree data from backend...');
    setIsLoading(true);
    try {
      // Reload individuals list
      const individualsResponse = await fetch('/api/individuals');
      if (individualsResponse.ok) {
        const data = await individualsResponse.json();
        setIndividuals(data.individuals);
        console.log('[TreePilot] Reloaded', data.individuals.length, 'individuals');
      }

      // Reload tree for selected person if any
      if (selectedPerson) {
        const personId = selectedPerson.id.replace(/@/g, '');
        const treeResponse = await fetch(`/api/tree/${personId}`);
        if (treeResponse.ok) {
          const data = await treeResponse.json();
          setTreeData(data.tree);
          console.log('[TreePilot] Reloaded tree for', selectedPerson.fullName);
        }
      }
    } catch (error) {
      console.error('[TreePilot] Failed to reload tree:', error);
    } finally {
      setIsLoading(false);
    }
  }, [selectedPerson]);

  // Download the modified GEDCOM file
  const handleDownloadGedcom = useCallback(async () => {
    console.log('[TreePilot] Downloading GEDCOM file...');
    try {
      const response = await fetch('/api/export-gedcom');
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'family-tree-export.ged';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        console.log('[TreePilot] GEDCOM download started');
      } else {
        console.error('[TreePilot] Failed to download GEDCOM:', response.statusText);
      }
    } catch (error) {
      console.error('[TreePilot] Failed to download GEDCOM:', error);
    }
  }, []);

  const handlePanelResize = useCallback((width: number) => {
    setChatPanelWidth(width);
  }, []);

  // Show import view if no GEDCOM loaded
  if (individuals.length === 0) {
    return (
      <div className="h-screen bg-slate-900 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="bg-slate-800 border-b border-slate-700 px-6 py-4 flex-shrink-0">
          <div className="flex items-center gap-3 max-w-7xl mx-auto">
            <TreeDeciduous className="w-8 h-8 text-emerald-500" />
            <div>
              <h1 className="text-2xl font-bold text-white">TreePilot</h1>
              <p className="text-sm text-slate-400">AI-Powered Genealogy Research</p>
            </div>
          </div>
        </header>

        {/* Import View */}
        <main className="flex-1 overflow-hidden">
          <div className="max-w-4xl mx-auto p-6">
            <GedcomImporter onLoaded={handleGedcomLoaded} />
          </div>
        </main>

        {/* Footer */}
        <footer className="bg-slate-800 border-t border-slate-700 px-6 py-3 flex-shrink-0">
          <div className="max-w-7xl mx-auto flex items-center justify-between text-sm text-slate-400">
            <span>Built with GitHub Copilot SDK for the Copilot SDK Contest</span>
            <a
              href="https://github.com/github/copilot-sdk"
              target="_blank"
              rel="noopener noreferrer"
              className="text-emerald-400 hover:text-emerald-300"
            >
              Powered by Copilot SDK
            </a>
          </div>
        </footer>
      </div>
    );
  }

  // Main split-pane view
  return (
    <div className="h-screen bg-slate-900 flex flex-col overflow-hidden">
      {/* Header */}
      <header className="bg-slate-800 border-b border-slate-700 px-6 py-4 flex-shrink-0">
        <div className="flex items-center justify-between max-w-full mx-auto">
          <div className="flex items-center gap-3">
            <TreeDeciduous className="w-8 h-8 text-emerald-500" />
            <div>
              <h1 className="text-2xl font-bold text-white">TreePilot</h1>
              <p className="text-sm text-slate-400">AI-Powered Genealogy Research</p>
            </div>
          </div>
          
          {/* Actions */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleReloadTree}
              disabled={isLoading}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              title="Reload tree data (picks up changes made by AI)"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
              Reload
            </button>
            <button
              onClick={handleDownloadGedcom}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
              title="Download modified GEDCOM file"
            >
              <Download className="w-4 h-4" />
              Export
            </button>
            <button
              onClick={() => {
                setIndividuals([]);
                setTreeData(null);
                setSelectedPerson(null);
              }}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
            >
              <Upload className="w-4 h-4" />
              Import New
            </button>
          </div>
        </div>
      </header>

      {/* Main Content - Split Pane: List | Tree | Chat */}
      <main ref={containerRef} className="flex-1 flex overflow-hidden">
        {/* Left Panel - Person List */}
        <aside className="w-64 bg-slate-800 border-r border-slate-700 flex flex-col min-h-0 flex-shrink-0">
          <div className="p-4 border-b border-slate-700 flex-shrink-0">
            <h2 className="text-lg font-semibold text-white">
              Individuals
              <span className="ml-2 text-sm font-normal text-slate-400">
                ({individuals.length})
              </span>
            </h2>
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            <div className="space-y-1">
              {individuals.map((person) => (
                <button
                  key={person.id}
                  onClick={() => handlePersonSelect(person)}
                  className={`w-full text-left p-2 rounded-lg transition-colors text-sm ${
                    selectedPerson?.id === person.id
                      ? 'bg-emerald-600 text-white'
                      : 'text-slate-300 hover:bg-slate-700'
                  }`}
                >
                  <div className="font-medium truncate">{person.fullName || 'Unknown'}</div>
                  <div className="text-xs opacity-75">
                    {person.birthYear && `b. ${person.birthYear}`}
                    {person.birthYear && person.deathYear && ' - '}
                    {person.deathYear && `d. ${person.deathYear}`}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </aside>

        {/* Middle Panel - Tree Visualization */}
        <div className="flex-1 relative overflow-hidden bg-slate-900">
          {isLoading ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="spinner w-12 h-12"></div>
            </div>
          ) : treeData ? (
            <AncestorTree
              data={treeData}
              onNodeClick={handleResearchPerson}
              selectedId={selectedPerson?.id}
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center text-slate-400">
              <div className="text-center">
                <TreeDeciduous className="w-16 h-16 mx-auto mb-4 opacity-50" />
                <p>Select a person from the list to view their ancestor tree</p>
              </div>
            </div>
          )}
        </div>

        {/* Resizable Divider */}
        <ResizableDivider
          onResize={handlePanelResize}
          minLeftWidth={400}
          maxLeftWidth={1200}
          containerRef={containerRef as React.RefObject<HTMLDivElement>}
        />

        {/* Right Panel - Chat */}
        <div
          className="flex-shrink-0 flex flex-col overflow-hidden border-l border-slate-700"
          style={{ width: chatPanelWidth }}
        >
          <Chat
            session={activeSession}
            sessions={sessions}
            onMessagesChange={handleMessagesChange}
            onSessionChange={handleSessionChange}
            onNewSession={handleNewSession}
            onDeleteSession={handleDeleteSession}
            onClearAllSessions={handleClearAllSessions}
          />
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-slate-800 border-t border-slate-700 px-6 py-2 flex-shrink-0">
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span>Built with GitHub Copilot SDK for the Copilot SDK Contest</span>
          <div className="flex items-center gap-4">
            <span>
              Created by smestern (
              <a
                href="https://www.smestern.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-emerald-400 hover:text-emerald-300"
              >
                find me here
              </a>
              )
            </span>
            <a
              href="https://github.com/github/copilot-sdk"
              target="_blank"
              rel="noopener noreferrer"
              className="text-emerald-400 hover:text-emerald-300"
            >
              Powered by Copilot SDK
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
