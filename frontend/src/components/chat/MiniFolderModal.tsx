import { useState } from 'react';
import { X, FolderPlus } from 'lucide-react';
import { supabase } from '../../lib/supabase';
import { useAuth } from '../../contexts/AuthContext';

interface MiniFolderModalProps {
  chatId: string;
  folderId: string;
  onClose: () => void;
  onSuccess: (miniFolderId: string) => void;
}

export function MiniFolderModal({ chatId, folderId, onClose, onSuccess }: MiniFolderModalProps) {
  const { user } = useAuth();
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user) return;

    setLoading(true);
    const { data, error } = await supabase
      .from('chats')
      .insert({
        folder_id: folderId,
        parent_chat_id: chatId,
        title: name,
        created_by: user.id,
        is_mini_folder: true,
      })
      .select()
      .single();

    if (!error && data) {
      await supabase.from('audit_logs').insert({
        user_id: user.id,
        action: 'create_mini_folder',
        resource_type: 'chat',
        resource_id: data.id,
        details: { name, parent_chat_id: chatId },
      });

      onSuccess(data.id);
    }

    setLoading(false);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="bg-medical-sage-100 p-2 rounded-lg">
              <FolderPlus className="w-5 h-5 text-medical-sage-600" />
            </div>
            <h3 className="text-xl font-serif font-semibold text-medical-navy-500">
              Create Mini-folder
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-medical-neutral-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-medical-neutral-600" />
          </button>
        </div>

        <p className="text-sm text-medical-neutral-600 mb-6">
          Mini-folders allow you to create nested chat threads for detailed case discussions. This
          helps organize complex cases that require multiple conversation threads.
        </p>

        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-medical-neutral-700 mb-1">
              Mini-folder Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-medical-neutral-300 rounded focus:outline-none focus:ring-2 focus:ring-medical-teal-500"
              placeholder="e.g., Follow-up imaging discussion"
              required
            />
          </div>

          <div className="bg-medical-teal-50 border border-medical-teal-200 rounded-lg p-3">
            <p className="text-sm text-medical-teal-800 leading-body">
              This mini-folder will be created as a continuation of the current chat. It will appear
              as a nested thread in the folder view.
            </p>
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="flex-1 px-4 py-2.5 border border-medical-neutral-300 rounded-lg text-medical-neutral-700 hover:bg-medical-neutral-50 transition-colors font-medium disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-4 py-2.5 bg-medical-navy-500 text-white rounded-lg hover:bg-medical-navy-600 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Creating...' : 'Create Mini-folder'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
