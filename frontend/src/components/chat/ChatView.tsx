import { useEffect, useState } from 'react';
import { ArrowLeft, Send, Paperclip, FolderPlus } from 'lucide-react';
import { supabase } from '../../lib/supabase';
import { Chat, MessageWithAI } from '../../lib/types';
import { useAuth } from '../../contexts/AuthContext';
import { ResearchSidebar } from './ResearchSidebar';

interface ChatViewProps {
  chatId: string;
  onBack: () => void;
  onCreateMiniFolderClick: () => void;
}

export function ChatView({ chatId, onBack, onCreateMiniFolderClick }: ChatViewProps) {
  const { user } = useAuth();
  const [chat, setChat] = useState<Chat | null>(null);
  const [messages, setMessages] = useState<MessageWithAI[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);

  useEffect(() => {
    loadChatData();
    const subscription = supabase
      .channel(`chat:${chatId}`)
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'messages',
          filter: `chat_id=eq.${chatId}`,
        },
        () => {
          loadChatData();
        }
      )
      .subscribe();

    return () => {
      subscription.unsubscribe();
    };
  }, [chatId]);

  const loadChatData = async () => {
    const { data: chatData } = await supabase.from('chats').select('*').eq('id', chatId).single();

    const { data: messagesData } = await supabase
      .from('messages')
      .select('*, ai_responses(*), research_papers(*)')
      .eq('chat_id', chatId)
      .order('created_at', { ascending: true });

    if (chatData) setChat(chatData);
    if (messagesData) {
      setMessages(messagesData as unknown as MessageWithAI[]);
      if (messagesData.length > 0 && !selectedMessageId) {
        const lastAiMessage = messagesData.reverse().find((m) => m.sender_type === 'ai_agent');
        if (lastAiMessage) setSelectedMessageId(lastAiMessage.id);
      }
    }
  };

  const sendMessage = async () => {
    if (!newMessage.trim() || !user || !chat) return;

    setSending(true);
    const { data: messageData, error } = await supabase
      .from('messages')
      .insert({
        chat_id: chat.id,
        sender_type: 'user',
        content: newMessage,
        attachments: [],
      })
      .select()
      .single();

    if (!error && messageData) {
      setNewMessage('');

      setTimeout(async () => {
        const aiResponse = generateMockAIResponse(newMessage);
        const { data: aiMessageData } = await supabase
          .from('messages')
          .insert({
            chat_id: chat.id,
            sender_type: 'ai_agent',
            content: aiResponse.content,
            attachments: [],
          })
          .select()
          .single();

        if (aiMessageData) {
          await supabase.from('ai_responses').insert({
            message_id: aiMessageData.id,
            primary_suggestion: aiResponse.primary_suggestion,
            confidence: aiResponse.confidence,
            differential_diagnoses: aiResponse.differential_diagnoses,
            red_flags: aiResponse.red_flags,
            missing_information: aiResponse.missing_information,
            reasoning_chain: aiResponse.reasoning_chain,
          });

          for (const paper of aiResponse.research_papers) {
            await supabase.from('research_papers').insert({
              message_id: aiMessageData.id,
              ...paper,
            });
          }

          setSelectedMessageId(aiMessageData.id);
        }
      }, 1500);
    }

    setSending(false);
  };

  if (!chat) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-medical-neutral-500">Loading chat...</div>
      </div>
    );
  }

  const selectedMessage = messages.find((m) => m.id === selectedMessageId);

  return (
    <div className="h-full flex">
      <div className="flex-1 flex flex-col bg-medical-neutral-50">
        <div className="bg-white border-b border-medical-neutral-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={onBack}
                className="p-2 hover:bg-medical-neutral-100 rounded-lg transition-colors"
              >
                <ArrowLeft className="w-5 h-5 text-medical-neutral-600" />
              </button>
              <div>
                <h2 className="text-lg font-semibold text-medical-navy-500">{chat.title}</h2>
                <p className="text-xs text-medical-neutral-500">{messages.length} messages</p>
              </div>
            </div>

            <button
              onClick={onCreateMiniFolderClick}
              className="flex items-center gap-2 px-3 py-2 border border-medical-neutral-300 rounded-lg hover:bg-medical-neutral-50 transition-colors text-sm font-medium text-medical-neutral-700"
            >
              <FolderPlus className="w-4 h-4" />
              Create Mini-folder
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-auto p-6 space-y-4">
          {messages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              isSelected={message.id === selectedMessageId}
              onClick={() => message.sender_type === 'ai_agent' && setSelectedMessageId(message.id)}
            />
          ))}
        </div>

        <div className="bg-white border-t border-medical-neutral-200 p-4">
          <div className="flex items-end gap-3">
            <button className="p-2.5 hover:bg-medical-neutral-100 rounded-lg transition-colors">
              <Paperclip className="w-5 h-5 text-medical-neutral-600" />
            </button>
            <textarea
              value={newMessage}
              onChange={(e) => setNewMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              placeholder="Describe the case or ask a question..."
              className="flex-1 px-4 py-3 border border-medical-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-medical-teal-500 resize-none"
              rows={3}
            />
            <button
              onClick={sendMessage}
              disabled={sending || !newMessage.trim()}
              className="p-3 bg-medical-navy-500 text-white rounded-lg hover:bg-medical-navy-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>

      <ResearchSidebar message={selectedMessage} />
    </div>
  );
}

function MessageBubble({
  message,
  isSelected,
  onClick,
}: {
  message: MessageWithAI;
  isSelected: boolean;
  onClick: () => void;
}) {
  const isAI = message.sender_type === 'ai_agent';
  const time = new Date(message.created_at).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <div className={`flex ${isAI ? 'justify-start' : 'justify-end'}`}>
      <button
        onClick={onClick}
        className={`max-w-2xl rounded-lg px-4 py-3 text-left transition-all ${
          isAI
            ? isSelected
              ? 'bg-medical-teal-50 border-2 border-medical-teal-300'
              : 'bg-white border border-medical-neutral-200 hover:border-medical-teal-200'
            : 'bg-medical-navy-500 text-white'
        }`}
      >
        <div className="flex items-start gap-3">
          {isAI && (
            <div className="w-7 h-7 bg-medical-teal-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-xs font-semibold text-medical-teal-700">AI</span>
            </div>
          )}
          <div className="flex-1">
            <p className={`text-sm leading-body ${isAI ? 'text-medical-neutral-800' : 'text-white'}`}>
              {message.content}
            </p>
            <p
              className={`text-xs mt-2 ${isAI ? 'text-medical-neutral-500' : 'text-medical-navy-100'}`}
            >
              {time}
            </p>
          </div>
        </div>
      </button>
    </div>
  );
}

function generateMockAIResponse(userMessage: string) {
  return {
    content:
      "Based on the symptoms you've described, I'm analyzing several possibilities. The patient presents with symptoms that could indicate multiple conditions. Let me break down my assessment.",
    primary_suggestion: 'Community-acquired pneumonia',
    confidence: 0.75,
    differential_diagnoses: [
      { diagnosis: 'Community-acquired pneumonia', probability: 0.75 },
      { diagnosis: 'Tuberculosis', probability: 0.15 },
      { diagnosis: 'Viral pneumonia', probability: 0.10 },
    ],
    red_flags: [
      'Persistent fever >3 days',
      'Oxygen saturation <92%',
      'Recent weight loss',
    ],
    missing_information: [
      'Complete blood count results',
      'Chest X-ray findings',
      'Recent travel history',
    ],
    reasoning_chain: [
      { step: 1, description: 'Patient reports chronic cough lasting 3 weeks with productive sputum' },
      { step: 2, description: 'Fever pattern suggests bacterial infection rather than viral' },
      { step: 3, description: 'Physical examination reveals crackles in lower right lung field' },
      { step: 4, description: 'Pattern consistent with community-acquired pneumonia, but TB cannot be ruled out without imaging' },
    ],
    research_papers: [
      {
        title: 'Community-Acquired Pneumonia: Diagnosis and Management in Adults',
        source: 'American Family Physician',
        tldr: 'Comprehensive review of CAP diagnosis criteria, emphasizing the importance of clinical presentation combined with radiographic findings. Discusses first-line antibiotic choices and when to escalate care.',
        url: 'https://example.com/paper1',
      },
      {
        title: 'Distinguishing Tuberculosis from Bacterial Pneumonia in Endemic Areas',
        source: 'The Lancet Infectious Diseases',
        tldr: 'Study comparing clinical features of TB vs bacterial pneumonia. Key differentiators include duration of symptoms, weight loss, and night sweats. Recommends AFB testing when symptoms persist >2 weeks.',
        url: 'https://example.com/paper2',
      },
    ],
  };
}
