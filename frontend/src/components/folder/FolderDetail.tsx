import { useEffect, useState } from 'react';
import { ArrowLeft, Plus, MessageSquare, Folder, Clock, Share2 } from 'lucide-react';
import { supabase } from '../../lib/supabase';
import { Folder as FolderType, ChatWithMessages } from '../../lib/types';
import { useAuth } from '../../contexts/AuthContext';

interface FolderDetailProps {
  folderId: string;
  onBack: () => void;
  onChatClick: (chatId: string) => void;
  onShareClick: () => void;
}

export function FolderDetail({ folderId, onBack, onChatClick, onShareClick }: FolderDetailProps) {
  const { user } = useAuth();
  const [folder, setFolder] = useState<FolderType | null>(null);
  const [chats, setChats] = useState<ChatWithMessages[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNewChatModal, setShowNewChatModal] = useState(false);

  useEffect(() => {
    loadFolderData();
  }, [folderId]);

  const loadFolderData = async () => {
    const { data: folderData } = await supabase
      .from('folders')
      .select('*')
      .eq('id', folderId)
      .single();

    const { data: chatsData } = await supabase
      .from('chats')
      .select('*, messages(count)')
      .eq('folder_id', folderId)
      .order('updated_at', { ascending: false });

    if (folderData) setFolder(folderData);
    if (chatsData) setChats(chatsData as unknown as ChatWithMessages[]);
    setLoading(false);
  };

  const createChat = async (title: string) => {
    if (!user || !folder) return;

    const { data, error } = await supabase
      .from('chats')
      .insert({
        folder_id: folder.id,
        title,
        created_by: user.id,
        is_mini_folder: false,
      })
      .select()
      .single();

    if (!error && data) {
      await supabase.from('audit_logs').insert({
        user_id: user.id,
        action: 'create_chat',
        resource_type: 'chat',
        resource_id: data.id,
        details: { title, folder_id: folder.id },
      });
      loadFolderData();
      setShowNewChatModal(false);
      onChatClick(data.id);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-medical-neutral-500">Loading folder...</div>
      </div>
    );
  }

  if (!folder) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-medical-neutral-500">Folder not found</div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="bg-white border-b border-medical-neutral-200 px-8 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={onBack}
              className="p-2 hover:bg-medical-neutral-100 rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5 text-medical-neutral-600" />
            </button>
            <div>
              <h2 className="text-2xl font-serif font-semibold text-medical-navy-500">
                {folder.name}
              </h2>
              <p className="text-sm text-medical-neutral-500 mt-1">{folder.specialty}</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={onShareClick}
              className="flex items-center gap-2 px-4 py-2.5 border border-medical-neutral-300 rounded-lg hover:bg-medical-neutral-50 transition-colors font-medium text-medical-neutral-700"
            >
              <Share2 className="w-4 h-4" />
              Share Folder
            </button>
            <button
              onClick={() => setShowNewChatModal(true)}
              className="flex items-center gap-2 bg-medical-navy-500 text-white px-4 py-2.5 rounded-lg hover:bg-medical-navy-600 transition-colors font-medium"
            >
              <Plus className="w-5 h-5" />
              New Chat
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-8">
        {chats.length === 0 ? (
          <div className="text-center py-16">
            <div className="bg-medical-neutral-100 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
              <MessageSquare className="w-8 h-8 text-medical-neutral-400" />
            </div>
            <h3 className="text-lg font-semibold text-medical-neutral-700 mb-2">No chats yet</h3>
            <p className="text-sm text-medical-neutral-500 mb-4">
              Start a new chat to begin your case discussion
            </p>
            <button
              onClick={() => setShowNewChatModal(true)}
              className="inline-flex items-center gap-2 bg-medical-navy-500 text-white px-4 py-2.5 rounded-lg hover:bg-medical-navy-600 transition-colors font-medium"
            >
              <Plus className="w-5 h-5" />
              Start Chat
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {chats.map((chat) => (
              <ChatCard key={chat.id} chat={chat} onClick={() => onChatClick(chat.id)} />
            ))}
          </div>
        )}
      </div>

      {showNewChatModal && (
        <NewChatModal onClose={() => setShowNewChatModal(false)} onCreate={createChat} />
      )}
    </div>
  );
}

function ChatCard({
  chat,
  onClick,
}: {
  chat: ChatWithMessages;
  onClick: () => void;
}) {
  const lastUpdated = new Date(chat.updated_at);
  const daysAgo = Math.floor((Date.now() - lastUpdated.getTime()) / (1000 * 60 * 60 * 24));

  return (
    <button
      onClick={onClick}
      className="bg-white border border-medical-neutral-200 rounded-lg p-5 hover:shadow-md hover:border-medical-teal-300 transition-all text-left group"
    >
      <div className="flex items-start gap-3 mb-3">
        <div className="bg-medical-teal-50 p-2.5 rounded-lg group-hover:bg-medical-teal-100 transition-colors">
          {chat.is_mini_folder ? (
            <Folder className="w-5 h-5 text-medical-teal-600" />
          ) : (
            <MessageSquare className="w-5 h-5 text-medical-teal-600" />
          )}
        </div>
        <div className="flex-1">
          <h3 className="text-base font-semibold text-medical-navy-500 mb-1 group-hover:text-medical-navy-600">
            {chat.title}
          </h3>
          {chat.is_mini_folder && (
            <span className="inline-block px-2 py-0.5 bg-medical-sage-50 border border-medical-sage-200 rounded text-xs font-medium text-medical-sage-700">
              Mini-folder
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-4 pt-3 border-t border-medical-neutral-100">
        <div className="flex items-center gap-1.5 text-medical-neutral-600">
          <MessageSquare className="w-4 h-4" />
          <span className="text-xs">{chat.message_count || 0} messages</span>
        </div>
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

function NewChatModal({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (title: string) => void;
}) {
  const [title, setTitle] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onCreate(title);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        <h3 className="text-xl font-serif font-semibold text-medical-navy-500 mb-4">
          Start New Chat
        </h3>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-medical-neutral-700 mb-1">
              Chat Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-3 py-2 border border-medical-neutral-300 rounded focus:outline-none focus:ring-2 focus:ring-medical-teal-500"
              placeholder="e.g., Initial diagnostic review"
              required
            />
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
              Start Chat
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
