import { useEffect, useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppLayout } from './components/layout/AppLayout';
import { PersonaGallery } from './components/personas/PersonaGallery';
import { ChatInterface } from './components/chat/ChatInterface';
import { KnowledgeGraph } from './components/graph/KnowledgeGraph';
import { usePersonaStore } from './stores/usePersonaStore';

type View = 'personas' | 'chat' | 'graph' | 'analytics';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 1,
    },
  },
});

function AppContent() {
  const [currentView, setCurrentView] = useState<View>('personas');
  const { selectedPersona } = usePersonaStore();

  useEffect(() => {
    // Only auto-switch right when persona becomes selected (null -> non-null)
    if (selectedPersona) {
      setCurrentView((prev) => (prev === 'personas' ? 'chat' : prev));
    }
  }, [selectedPersona]);

  const renderView = () => {
    switch (currentView) {
      case 'personas':
        return <PersonaGallery />;
      case 'chat':
        return <ChatInterface />;
      case 'graph':
        return <KnowledgeGraph />;
      case 'analytics':
        return (
          <div className="flex items-center justify-center h-full">
            <p className="text-dark-500">Analytics coming soon...</p>
          </div>
        );
      default:
        return <PersonaGallery />;
    }
  };

  return (
    <AppLayout currentView={currentView} onViewChange={setCurrentView}>
      {renderView()}
    </AppLayout>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
}
