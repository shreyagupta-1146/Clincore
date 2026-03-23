import { useState } from 'react';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { LoginPage } from './components/auth/LoginPage';
import { MainLayout } from './components/layout/MainLayout';
import { Dashboard } from './components/dashboard/Dashboard';
import { FolderDetail } from './components/folder/FolderDetail';
import { ChatView } from './components/chat/ChatView';
import { MiniFolderModal } from './components/chat/MiniFolderModal';
import { ShareFolderModal } from './components/sharing/ShareFolderModal';
import { AuditLogView } from './components/settings/AuditLogView';
import { SettingsView } from './components/settings/SettingsView';

type View = 'dashboard' | 'folders' | 'audit' | 'settings';

interface AppState {
  view: View;
  selectedFolderId: string | null;
  selectedChatId: string | null;
  folderName: string;
  showShareModal: boolean;
  showMiniFolderModal: boolean;
}

function AppContent() {
  const { user, loading } = useAuth();
  const [state, setState] = useState<AppState>({
    view: 'dashboard',
    selectedFolderId: null,
    selectedChatId: null,
    folderName: '',
    showShareModal: false,
    showMiniFolderModal: false,
  });

  const handleViewChange = (view: View) => {
    setState((prev) => ({
      ...prev,
      view,
      selectedFolderId: null,
      selectedChatId: null,
    }));
  };

  const handleFolderClick = (folderId: string) => {
    setState((prev) => ({
      ...prev,
      selectedFolderId: folderId,
      selectedChatId: null,
    }));
  };

  const handleChatClick = (chatId: string) => {
    setState((prev) => ({
      ...prev,
      selectedChatId: chatId,
    }));
  };

  const handleBackToDashboard = () => {
    setState((prev) => ({
      ...prev,
      selectedFolderId: null,
      selectedChatId: null,
    }));
  };

  const handleBackToFolder = () => {
    setState((prev) => ({
      ...prev,
      selectedChatId: null,
    }));
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-medical-neutral-50 flex items-center justify-center">
        <div className="text-medical-neutral-500">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  const getHeaderConfig = () => {
    if (state.selectedChatId) {
      return { title: 'Chat', subtitle: 'Discussion thread', showSearch: false };
    }
    if (state.selectedFolderId) {
      return { title: 'Folder', subtitle: 'Case files and chats', showSearch: false };
    }
    if (state.view === 'audit') {
      return { title: 'Audit Logs', subtitle: 'Security and activity monitoring', showSearch: false };
    }
    if (state.view === 'settings') {
      return { title: 'Settings', subtitle: 'Account preferences', showSearch: false };
    }
    return { title: 'Dashboard', subtitle: 'Medical case management', showSearch: true };
  };

  const headerConfig = getHeaderConfig();

  return (
    <>
      <MainLayout
        currentView={state.view}
        onViewChange={handleViewChange}
        headerTitle={headerConfig.title}
        headerSubtitle={headerConfig.subtitle}
        showSearch={headerConfig.showSearch}
      >
        {state.selectedChatId && state.selectedFolderId ? (
          <ChatView
            chatId={state.selectedChatId}
            onBack={handleBackToFolder}
            onCreateMiniFolderClick={() =>
              setState((prev) => ({ ...prev, showMiniFolderModal: true }))
            }
          />
        ) : state.selectedFolderId ? (
          <FolderDetail
            folderId={state.selectedFolderId}
            onBack={handleBackToDashboard}
            onChatClick={handleChatClick}
            onShareClick={() => setState((prev) => ({ ...prev, showShareModal: true }))}
          />
        ) : state.view === 'audit' ? (
          <AuditLogView />
        ) : state.view === 'settings' ? (
          <SettingsView />
        ) : (
          <Dashboard onFolderClick={handleFolderClick} />
        )}
      </MainLayout>

      {state.showShareModal && state.selectedFolderId && (
        <ShareFolderModal
          folderId={state.selectedFolderId}
          folderName={state.folderName}
          onClose={() => setState((prev) => ({ ...prev, showShareModal: false }))}
          onSuccess={() => setState((prev) => ({ ...prev, showShareModal: false }))}
        />
      )}

      {state.showMiniFolderModal && state.selectedChatId && state.selectedFolderId && (
        <MiniFolderModal
          chatId={state.selectedChatId}
          folderId={state.selectedFolderId}
          onClose={() => setState((prev) => ({ ...prev, showMiniFolderModal: false }))}
          onSuccess={(miniFolderId) => {
            setState((prev) => ({ ...prev, showMiniFolderModal: false }));
            handleChatClick(miniFolderId);
          }}
        />
      )}
    </>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
