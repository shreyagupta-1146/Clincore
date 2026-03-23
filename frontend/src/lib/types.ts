export type Database = {
  public: {
    Tables: {
      folders: {
        Row: {
          id: string;
          name: string;
          owner_id: string;
          specialty: string;
          status: 'Pending review' | 'Shared' | 'Private';
          requires_auth: boolean;
          created_at: string;
          updated_at: string;
        };
        Insert: Omit<Database['public']['Tables']['folders']['Row'], 'id' | 'created_at' | 'updated_at'>;
        Update: Partial<Database['public']['Tables']['folders']['Insert']>;
      };
      chats: {
        Row: {
          id: string;
          folder_id: string;
          parent_chat_id: string | null;
          title: string;
          is_mini_folder: boolean;
          created_by: string;
          created_at: string;
          updated_at: string;
        };
        Insert: Omit<Database['public']['Tables']['chats']['Row'], 'id' | 'created_at' | 'updated_at'>;
        Update: Partial<Database['public']['Tables']['chats']['Insert']>;
      };
      messages: {
        Row: {
          id: string;
          chat_id: string;
          sender_type: 'user' | 'ai_agent';
          content: string;
          attachments: Array<{
            name: string;
            type: string;
            url: string;
          }>;
          created_at: string;
        };
        Insert: Omit<Database['public']['Tables']['messages']['Row'], 'id' | 'created_at'>;
        Update: Partial<Database['public']['Tables']['messages']['Insert']>;
      };
      ai_responses: {
        Row: {
          id: string;
          message_id: string;
          primary_suggestion: string | null;
          confidence: number | null;
          differential_diagnoses: Array<{
            diagnosis: string;
            probability: number;
          }>;
          red_flags: Array<string>;
          missing_information: Array<string>;
          reasoning_chain: Array<{
            step: number;
            description: string;
          }>;
          created_at: string;
        };
        Insert: Omit<Database['public']['Tables']['ai_responses']['Row'], 'id' | 'created_at'>;
        Update: Partial<Database['public']['Tables']['ai_responses']['Insert']>;
      };
      research_papers: {
        Row: {
          id: string;
          message_id: string;
          title: string;
          source: string | null;
          tldr: string | null;
          url: string | null;
          created_at: string;
        };
        Insert: Omit<Database['public']['Tables']['research_papers']['Row'], 'id' | 'created_at'>;
        Update: Partial<Database['public']['Tables']['research_papers']['Insert']>;
      };
      folder_shares: {
        Row: {
          id: string;
          folder_id: string;
          shared_by: string;
          shared_with_email: string;
          shared_with_name: string;
          shared_with_role: string | null;
          created_at: string;
        };
        Insert: Omit<Database['public']['Tables']['folder_shares']['Row'], 'id' | 'created_at'>;
        Update: Partial<Database['public']['Tables']['folder_shares']['Insert']>;
      };
      audit_logs: {
        Row: {
          id: string;
          user_id: string;
          action: string;
          resource_type: 'folder' | 'chat' | 'message' | 'share' | 'auth';
          resource_id: string | null;
          details: Record<string, unknown>;
          created_at: string;
        };
        Insert: Omit<Database['public']['Tables']['audit_logs']['Row'], 'id' | 'created_at'>;
        Update: Partial<Database['public']['Tables']['audit_logs']['Insert']>;
      };
    };
  };
};

export type Folder = Database['public']['Tables']['folders']['Row'];
export type Chat = Database['public']['Tables']['chats']['Row'];
export type Message = Database['public']['Tables']['messages']['Row'];
export type AIResponse = Database['public']['Tables']['ai_responses']['Row'];
export type ResearchPaper = Database['public']['Tables']['research_papers']['Row'];
export type FolderShare = Database['public']['Tables']['folder_shares']['Row'];
export type AuditLog = Database['public']['Tables']['audit_logs']['Row'];

export interface FolderWithShares extends Folder {
  folder_shares: FolderShare[];
  chat_count?: number;
  last_updated?: string;
}

export interface ChatWithMessages extends Chat {
  messages: Message[];
  message_count?: number;
}

export interface MessageWithAI extends Message {
  ai_responses: AIResponse[];
  research_papers: ResearchPaper[];
}
