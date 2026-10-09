import { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatPanel } from './components/ChatPanel';
import { DocumentUploadPage } from './components/DocumentUploadPage';
import { useChat } from './hooks/useChat';

// ─── App ──────────────────────────────────────────────────────────────────────

function App() {
  const [currentView, setCurrentView] = useState<'chat' | 'upload'>('chat');

  const {
    messages,
    isLoading,
    conversations,
    sendChatMessage,
    clearConversation,
  } = useChat();

  return (
    <div className="flex h-screen w-full overflow-hidden font-sans bg-stone-100">
      {/* Sidebar */}
      <Sidebar
        conversations={conversations}
        currentView={currentView}
        onViewChange={setCurrentView}
        onNewChat={() => {
          clearConversation();
          setCurrentView('chat');
        }}
      />

      {/* Main Content Area */}
      <main className="flex-1 w-full h-full flex flex-col overflow-hidden min-w-0">
        {currentView === 'chat' && (
          <ChatPanel
            messages={messages}
            isLoading={isLoading}
            onSendMessage={sendChatMessage}
            onClear={clearConversation}
            onOpenUpload={() => setCurrentView('upload')}
          />
        )}

        {currentView === 'upload' && (
          <DocumentUploadPage onBackToChat={() => setCurrentView('chat')} />
        )}
      </main>
    </div>
  );
}

export default App;
