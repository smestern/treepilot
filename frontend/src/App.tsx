import { useState, useCallback } from 'react';
import { TreeDeciduous, Upload, MessageSquare, Users } from 'lucide-react';
import Chat from './components/Chat';
import GedcomImporter from './components/GedcomImporter';
import AncestorTree from './components/AncestorTree';
import { Individual, TreeNode } from './types';

function App() {
  const [individuals, setIndividuals] = useState<Individual[]>([]);
  const [selectedPerson, setSelectedPerson] = useState<Individual | null>(null);
  const [treeData, setTreeData] = useState<TreeNode | null>(null);
  const [activeTab, setActiveTab] = useState<'import' | 'tree' | 'chat'>('import');
  const [isLoading, setIsLoading] = useState(false);

  const handleGedcomLoaded = useCallback((loadedIndividuals: Individual[]) => {
    console.log('[TreePilot] GEDCOM loaded with', loadedIndividuals.length, 'individuals');
    console.log('[TreePilot] First few individuals:', loadedIndividuals.slice(0, 3));
    setIndividuals(loadedIndividuals);
    // Auto-select first person and switch to tree view
    if (loadedIndividuals.length > 0) {
      setActiveTab('tree');
    }
  }, []);

  const handlePersonSelect = useCallback(async (person: Individual) => {
    console.log('[TreePilot] Person selected:', person.fullName, 'ID:', person.id);
    setSelectedPerson(person);
    setIsLoading(true);

    try {
      // Fetch ancestor tree for this person
      const personId = person.id.replace(/@/g, '');
      console.log('[TreePilot] Fetching tree for personId:', personId);
      const response = await fetch(`/api/tree/${personId}`);
      
      console.log('[TreePilot] Tree API response status:', response.status);
      
      if (response.ok) {
        const data = await response.json();
        console.log('[TreePilot] Tree data received:', data);
        console.log('[TreePilot] Tree structure:', JSON.stringify(data.tree, null, 2).substring(0, 500) + '...');
        setTreeData(data.tree);
      } else {
        const errorText = await response.text();
        console.error('[TreePilot] Tree API error response:', errorText);
      }
    } catch (error) {
      console.error('[TreePilot] Failed to fetch tree:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleResearchPerson = useCallback((person: Individual) => {
    setSelectedPerson(person);
    setActiveTab('chat');
  }, []);

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col">
      {/* Header */}
      <header className="bg-slate-800 border-b border-slate-700 px-6 py-4">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-3">
            <TreeDeciduous className="w-8 h-8 text-emerald-500" />
            <div>
              <h1 className="text-2xl font-bold text-white">TreePilot</h1>
              <p className="text-sm text-slate-400">AI-Powered Genealogy Research</p>
            </div>
          </div>
          
          {/* Tab Navigation */}
          <nav className="flex gap-2">
            <button
              onClick={() => setActiveTab('import')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                activeTab === 'import'
                  ? 'bg-emerald-600 text-white'
                  : 'text-slate-400 hover:text-white hover:bg-slate-700'
              }`}
            >
              <Upload className="w-4 h-4" />
              Import
            </button>
            <button
              onClick={() => setActiveTab('tree')}
              disabled={individuals.length === 0}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                activeTab === 'tree'
                  ? 'bg-emerald-600 text-white'
                  : 'text-slate-400 hover:text-white hover:bg-slate-700'
              } ${individuals.length === 0 ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <Users className="w-4 h-4" />
              Tree
              {individuals.length > 0 && (
                <span className="bg-slate-700 px-2 py-0.5 rounded-full text-xs">
                  {individuals.length}
                </span>
              )}
            </button>
            <button
              onClick={() => setActiveTab('chat')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                activeTab === 'chat'
                  ? 'bg-emerald-600 text-white'
                  : 'text-slate-400 hover:text-white hover:bg-slate-700'
              }`}
            >
              <MessageSquare className="w-4 h-4" />
              Research
            </button>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-hidden">
        {activeTab === 'import' && (
          <div className="max-w-4xl mx-auto p-6">
            <GedcomImporter onLoaded={handleGedcomLoaded} />
          </div>
        )}

        {activeTab === 'tree' && (
          <div className="h-full flex">
            {/* Sidebar - Person List */}
            <aside className="w-80 bg-slate-800 border-r border-slate-700 overflow-y-auto">
              <div className="p-4">
                <h2 className="text-lg font-semibold text-white mb-4">Individuals</h2>
                <div className="space-y-2">
                  {individuals.map((person) => (
                    <button
                      key={person.id}
                      onClick={() => handlePersonSelect(person)}
                      className={`w-full text-left p-3 rounded-lg transition-colors ${
                        selectedPerson?.id === person.id
                          ? 'bg-emerald-600 text-white'
                          : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                      }`}
                    >
                      <div className="font-medium">{person.fullName || 'Unknown'}</div>
                      <div className="text-sm opacity-75">
                        {person.birthYear && `b. ${person.birthYear}`}
                        {person.birthYear && person.deathYear && ' - '}
                        {person.deathYear && `d. ${person.deathYear}`}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </aside>

            {/* Tree Visualization */}
            <div className="flex-1 relative">
              {(() => {
                console.log('[TreePilot] Tree render state - isLoading:', isLoading, 'treeData:', treeData ? 'present' : 'null');
                return null;
              })()}
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
                    <Users className="w-16 h-16 mx-auto mb-4 opacity-50" />
                    <p>Select a person from the list to view their ancestor tree</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'chat' && (
          <div className="h-full max-w-4xl mx-auto">
            <Chat selectedPerson={selectedPerson} />
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-slate-800 border-t border-slate-700 px-6 py-3">
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

export default App;
