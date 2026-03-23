import { ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';

interface MainLayoutProps {
  children: ReactNode;
  currentView: 'dashboard' | 'folders' | 'audit' | 'settings';
  onViewChange: (view: 'dashboard' | 'folders' | 'audit' | 'settings') => void;
  headerTitle: string;
  headerSubtitle?: string;
  showSearch?: boolean;
  onSearch?: (query: string) => void;
}

export function MainLayout({
  children,
  currentView,
  onViewChange,
  headerTitle,
  headerSubtitle,
  showSearch,
  onSearch,
}: MainLayoutProps) {
  return (
    <div className="flex h-screen bg-medical-neutral-50">
      <Sidebar currentView={currentView} onViewChange={onViewChange} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header
          title={headerTitle}
          subtitle={headerSubtitle}
          showSearch={showSearch}
          onSearch={onSearch}
        />
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
