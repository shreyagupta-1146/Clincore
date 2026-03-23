import { useEffect, useState } from 'react';
import { Plus, Filter } from 'lucide-react';
import { supabase } from '../../lib/supabase';
import { FolderWithShares } from '../../lib/types';
import { useAuth } from '../../contexts/AuthContext';
import { FolderCard } from './FolderCard';

interface DashboardProps {
  onFolderClick: (folderId: string) => void;
}

const SPECIALTIES = [
  'All',
  'General Medicine',
  'Cardiology',
  'Oncology',
  'Neurology',
  'Pediatrics',
  'Radiology',
];

export function Dashboard({ onFolderClick }: DashboardProps) {
  const { user } = useAuth();
  const [folders, setFolders] = useState<FolderWithShares[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedSpecialty, setSelectedSpecialty] = useState('All');
  const [showNewFolderModal, setShowNewFolderModal] = useState(false);

  useEffect(() => {
    loadFolders();
  }, [user]);

  const loadFolders = async () => {
    if (!user) return;

    const { data, error } = await supabase
      .from('folders')
      .select('*, folder_shares(*)')
      .order('updated_at', { ascending: false });

    if (!error && data) {
      setFolders(data as FolderWithShares[]);
    }
    setLoading(false);
  };

  const createFolder = async (name: string, specialty: string) => {
    if (!user) return;

    const { error } = await supabase.from('folders').insert({
      name,
      specialty,
      owner_id: user.id,
      status: 'Private',
      requires_auth: false,
    });

    if (!error) {
      await supabase.from('audit_logs').insert({
        user_id: user.id,
        action: 'create_folder',
        resource_type: 'folder',
        details: { name, specialty },
      });
      loadFolders();
      setShowNewFolderModal(false);
    }
  };

  const filteredFolders =
    selectedSpecialty === 'All'
      ? folders
      : folders.filter((f) => f.specialty === selectedSpecialty);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-medical-neutral-500">Loading folders...</div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Filter className="w-5 h-5 text-medical-neutral-600" />
          <div className="flex gap-2">
            {SPECIALTIES.map((specialty) => (
              <button
                key={specialty}
                onClick={() => setSelectedSpecialty(specialty)}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  selectedSpecialty === specialty
                    ? 'bg-medical-navy-500 text-white'
                    : 'bg-white border border-medical-neutral-200 text-medical-neutral-700 hover:border-medical-teal-300'
                }`}
              >
                {specialty}
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={() => setShowNewFolderModal(true)}
          className="flex items-center gap-2 bg-medical-navy-500 text-white px-4 py-2.5 rounded-lg hover:bg-medical-navy-600 transition-colors font-medium"
        >
          <Plus className="w-5 h-5" />
          New Folder
        </button>
      </div>

      {filteredFolders.length === 0 ? (
        <div className="text-center py-16">
          <div className="bg-medical-neutral-100 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
            <FolderCard className="w-8 h-8 text-medical-neutral-400" />
          </div>
          <h3 className="text-lg font-semibold text-medical-neutral-700 mb-2">No folders yet</h3>
          <p className="text-sm text-medical-neutral-500 mb-4">
            Create your first folder to start organizing cases
          </p>
          <button
            onClick={() => setShowNewFolderModal(true)}
            className="inline-flex items-center gap-2 bg-medical-navy-500 text-white px-4 py-2.5 rounded-lg hover:bg-medical-navy-600 transition-colors font-medium"
          >
            <Plus className="w-5 h-5" />
            Create Folder
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredFolders.map((folder) => (
            <FolderCard key={folder.id} folder={folder} onClick={() => onFolderClick(folder.id)} />
          ))}
        </div>
      )}

      {showNewFolderModal && (
        <NewFolderModal
          onClose={() => setShowNewFolderModal(false)}
          onCreate={createFolder}
          specialties={SPECIALTIES.filter((s) => s !== 'All')}
        />
      )}
    </div>
  );
}

function NewFolderModal({
  onClose,
  onCreate,
  specialties,
}: {
  onClose: () => void;
  specialties: string[];
  onCreate: (name: string, specialty: string) => void;
}) {
  const [name, setName] = useState('');
  const [specialty, setSpecialty] = useState(specialties[0]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onCreate(name, specialty);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        <h3 className="text-xl font-serif font-semibold text-medical-navy-500 mb-4">
          Create New Folder
        </h3>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-medical-neutral-700 mb-1">
              Folder Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-medical-neutral-300 rounded focus:outline-none focus:ring-2 focus:ring-medical-teal-500"
              placeholder="e.g., Pneumonia vs TB Case Review"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-medical-neutral-700 mb-1">
              Specialty
            </label>
            <select
              value={specialty}
              onChange={(e) => setSpecialty(e.target.value)}
              className="w-full px-3 py-2 border border-medical-neutral-300 rounded focus:outline-none focus:ring-2 focus:ring-medical-teal-500"
            >
              {specialties.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2.5 border border-medical-neutral-300 rounded-lg text-medical-neutral-700 hover:bg-medical-neutral-50 transition-colors font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2.5 bg-medical-navy-500 text-white rounded-lg hover:bg-medical-navy-600 transition-colors font-medium"
            >
              Create Folder
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
