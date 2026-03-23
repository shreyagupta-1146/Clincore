import { FolderOpen, FileText, Shield, Settings, LogOut } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

interface SidebarProps {
  currentView: 'dashboard' | 'folders' | 'audit' | 'settings';
  onViewChange: (view: 'dashboard' | 'folders' | 'audit' | 'settings') => void;
}

export function Sidebar({ currentView, onViewChange }: SidebarProps) {
  const { signOut } = useAuth();

  const navItems = [
    { id: 'dashboard' as const, label: 'Dashboard', icon: FolderOpen },
    { id: 'folders' as const, label: 'Folders', icon: FileText },
    { id: 'audit' as const, label: 'Audit Logs', icon: Shield },
    { id: 'settings' as const, label: 'Settings', icon: Settings },
  ];

  return (
    <aside className="w-64 bg-white border-r border-medical-neutral-200 flex flex-col h-screen">
      <div className="p-6 border-b border-medical-neutral-200">
        <div className="flex items-center gap-3">
          <div className="bg-medical-navy-500 p-2 rounded-lg">
            <Shield className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-serif font-semibold text-medical-navy-500">Medical AI</h1>
            <p className="text-xs text-medical-neutral-500">Clinical Platform</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-4">
        <ul className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentView === item.id;
            return (
              <li key={item.id}>
                <button
                  onClick={() => onViewChange(item.id)}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg transition-colors ${
                    isActive
                      ? 'bg-medical-navy-500 text-white'
                      : 'text-medical-neutral-700 hover:bg-medical-neutral-100'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span className="font-medium text-sm">{item.label}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="p-4 border-t border-medical-neutral-200">
        <button
          onClick={signOut}
          className="w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-medical-neutral-700 hover:bg-medical-neutral-100 transition-colors"
        >
          <LogOut className="w-5 h-5" />
          <span className="font-medium text-sm">Sign Out</span>
        </button>
      </div>
    </aside>
  );
}
