import { Search, Bell, Shield } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

interface HeaderProps {
  title: string;
  subtitle?: string;
  showSearch?: boolean;
  onSearch?: (query: string) => void;
}

export function Header({ title, subtitle, showSearch = false, onSearch }: HeaderProps) {
  const { user } = useAuth();

  return (
    <header className="bg-white border-b border-medical-neutral-200 px-8 py-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-serif font-semibold text-medical-navy-500">{title}</h2>
          {subtitle && <p className="text-sm text-medical-neutral-500 mt-1">{subtitle}</p>}
        </div>

        <div className="flex items-center gap-4">
          {showSearch && (
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-medical-neutral-400" />
              <input
                type="text"
                placeholder="Search folders, cases..."
                onChange={(e) => onSearch?.(e.target.value)}
                className="pl-10 pr-4 py-2 w-80 border border-medical-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-medical-teal-500 focus:border-transparent text-sm"
              />
            </div>
          )}

          <div className="flex items-center gap-2 px-3 py-1.5 bg-medical-teal-50 border border-medical-teal-200 rounded-lg">
            <Shield className="w-4 h-4 text-medical-teal-600" />
            <span className="text-xs font-medium text-medical-teal-700">Encrypted</span>
          </div>

          <button className="relative p-2 hover:bg-medical-neutral-100 rounded-lg transition-colors">
            <Bell className="w-5 h-5 text-medical-neutral-600" />
            <span className="absolute top-1 right-1 w-2 h-2 bg-error rounded-full"></span>
          </button>

          <div className="flex items-center gap-2 pl-4 border-l border-medical-neutral-200">
            <div className="w-8 h-8 bg-medical-sage-500 rounded-full flex items-center justify-center">
              <span className="text-white text-sm font-medium">
                {user?.email?.[0].toUpperCase() || 'U'}
              </span>
            </div>
            <div className="text-right">
              <p className="text-sm font-medium text-medical-neutral-700">
                {user?.user_metadata?.name || 'User'}
              </p>
              <p className="text-xs text-medical-neutral-500">Physician</p>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
