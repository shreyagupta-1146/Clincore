import { FolderOpen, Lock, Users, Clock } from 'lucide-react';
import { FolderWithShares } from '../../lib/types';

interface FolderCardProps {
  folder: FolderWithShares;
  onClick: () => void;
}

export function FolderCard({ folder, onClick }: FolderCardProps) {
  const shareCount = folder.folder_shares?.length || 0;
  const lastUpdated = new Date(folder.updated_at);
  const daysAgo = Math.floor((Date.now() - lastUpdated.getTime()) / (1000 * 60 * 60 * 24));

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'Shared':
        return 'bg-medical-teal-50 text-medical-teal-700 border-medical-teal-200';
      case 'Pending review':
        return 'bg-warning-light/10 text-warning-dark border-warning-light';
      default:
        return 'bg-medical-neutral-100 text-medical-neutral-700 border-medical-neutral-200';
    }
  };

  return (
    <button
      onClick={onClick}
      className="w-full bg-white border border-medical-neutral-200 rounded-lg p-5 hover:shadow-md hover:border-medical-teal-300 transition-all text-left group"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="bg-medical-navy-50 p-2.5 rounded-lg group-hover:bg-medical-navy-100 transition-colors">
            <FolderOpen className="w-5 h-5 text-medical-navy-500" />
          </div>
          {folder.requires_auth && (
            <div className="flex items-center gap-1 px-2 py-1 bg-medical-teal-50 border border-medical-teal-200 rounded">
              <Lock className="w-3 h-3 text-medical-teal-600" />
              <span className="text-xs font-medium text-medical-teal-700">Secured</span>
            </div>
          )}
        </div>
        <span
          className={`px-2.5 py-1 border rounded text-xs font-medium ${getStatusColor(folder.status)}`}
        >
          {folder.status}
        </span>
      </div>

      <h3 className="text-base font-semibold text-medical-navy-500 mb-1 group-hover:text-medical-navy-600">
        {folder.name}
      </h3>
      <p className="text-sm text-medical-neutral-500 mb-4">{folder.specialty}</p>

      <div className="flex items-center gap-4 pt-3 border-t border-medical-neutral-100">
        {shareCount > 0 && (
          <div className="flex items-center gap-1.5 text-medical-neutral-600">
            <Users className="w-4 h-4" />
            <span className="text-xs">Shared with {shareCount} {shareCount === 1 ? 'specialist' : 'specialists'}</span>
          </div>
        )}
        <div className="flex items-center gap-1.5 text-medical-neutral-600">
          <Clock className="w-4 h-4" />
          <span className="text-xs">
            {daysAgo === 0 ? 'Today' : daysAgo === 1 ? 'Yesterday' : `${daysAgo} days ago`}
          </span>
        </div>
      </div>
    </button>
  );
}
