/*
  # Medical AI-Agent Platform Database Schema

  ## Overview
  This migration creates the complete database schema for a secure, multi-modal medical AI-agents platform
  used by doctors and clinical teams.

  ## New Tables
  1. folders - Main organizational unit for medical cases
  2. chats - Individual chat threads within folders
  3. messages - Individual messages within chats
  4. ai_responses - Structured AI response data with explainability
  5. research_papers - Similar cases and research papers
  6. folder_shares - Tracks folder sharing
  7. audit_logs - Security and activity audit trail

  ## Security
  - Enable RLS on all tables
  - Comprehensive access control policies
*/

-- Folders table
CREATE TABLE IF NOT EXISTS folders (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  owner_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  specialty text DEFAULT 'General Medicine',
  status text DEFAULT 'Private' CHECK (status IN ('Pending review', 'Shared', 'Private')),
  requires_auth boolean DEFAULT false,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Chats table
CREATE TABLE IF NOT EXISTS chats (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  folder_id uuid NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
  parent_chat_id uuid REFERENCES chats(id) ON DELETE CASCADE,
  title text NOT NULL,
  is_mini_folder boolean DEFAULT false,
  created_by uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Messages table
CREATE TABLE IF NOT EXISTS messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id uuid NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
  sender_type text NOT NULL CHECK (sender_type IN ('user', 'ai_agent')),
  content text NOT NULL,
  attachments jsonb DEFAULT '[]'::jsonb,
  created_at timestamptz DEFAULT now()
);

-- AI Responses table
CREATE TABLE IF NOT EXISTS ai_responses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  message_id uuid NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  primary_suggestion text,
  confidence numeric CHECK (confidence >= 0 AND confidence <= 1),
  differential_diagnoses jsonb DEFAULT '[]'::jsonb,
  red_flags jsonb DEFAULT '[]'::jsonb,
  missing_information jsonb DEFAULT '[]'::jsonb,
  reasoning_chain jsonb DEFAULT '[]'::jsonb,
  created_at timestamptz DEFAULT now()
);

-- Research Papers table
CREATE TABLE IF NOT EXISTS research_papers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  message_id uuid NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  title text NOT NULL,
  source text,
  tldr text,
  url text,
  created_at timestamptz DEFAULT now()
);

-- Folder Shares table
CREATE TABLE IF NOT EXISTS folder_shares (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  folder_id uuid NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
  shared_by uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  shared_with_email text NOT NULL,
  shared_with_name text NOT NULL,
  shared_with_role text,
  created_at timestamptz DEFAULT now()
);

-- Audit Logs table
CREATE TABLE IF NOT EXISTS audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  action text NOT NULL,
  resource_type text NOT NULL CHECK (resource_type IN ('folder', 'chat', 'message', 'share', 'auth')),
  resource_id uuid,
  details jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz DEFAULT now()
);

-- Enable RLS
ALTER TABLE folders ENABLE ROW LEVEL SECURITY;
ALTER TABLE chats ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_papers ENABLE ROW LEVEL SECURITY;
ALTER TABLE folder_shares ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Folders policies
CREATE POLICY "Users can view own and shared folders"
  ON folders FOR SELECT
  TO authenticated
  USING (
    auth.uid() = owner_id 
    OR EXISTS (
      SELECT 1 FROM folder_shares 
      WHERE folder_shares.folder_id = folders.id 
      AND folder_shares.shared_with_email = (SELECT email FROM auth.users WHERE id = auth.uid())
    )
  );

CREATE POLICY "Users can create own folders"
  ON folders FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = owner_id);

CREATE POLICY "Users can update own folders"
  ON folders FOR UPDATE
  TO authenticated
  USING (auth.uid() = owner_id)
  WITH CHECK (auth.uid() = owner_id);

CREATE POLICY "Users can delete own folders"
  ON folders FOR DELETE
  TO authenticated
  USING (auth.uid() = owner_id);

-- Chats policies
CREATE POLICY "Users can view chats in accessible folders"
  ON chats FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM folders 
      WHERE folders.id = chats.folder_id 
      AND (
        folders.owner_id = auth.uid() 
        OR EXISTS (
          SELECT 1 FROM folder_shares 
          WHERE folder_shares.folder_id = folders.id 
          AND folder_shares.shared_with_email = (SELECT email FROM auth.users WHERE id = auth.uid())
        )
      )
    )
  );

CREATE POLICY "Users can create chats in own folders"
  ON chats FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (SELECT 1 FROM folders WHERE folders.id = chats.folder_id AND folders.owner_id = auth.uid())
    AND auth.uid() = created_by
  );

CREATE POLICY "Users can update chats in own folders"
  ON chats FOR UPDATE
  TO authenticated
  USING (EXISTS (SELECT 1 FROM folders WHERE folders.id = chats.folder_id AND folders.owner_id = auth.uid()))
  WITH CHECK (EXISTS (SELECT 1 FROM folders WHERE folders.id = chats.folder_id AND folders.owner_id = auth.uid()));

CREATE POLICY "Users can delete chats in own folders"
  ON chats FOR DELETE
  TO authenticated
  USING (EXISTS (SELECT 1 FROM folders WHERE folders.id = chats.folder_id AND folders.owner_id = auth.uid()));

-- Messages policies
CREATE POLICY "Users can view messages in accessible chats"
  ON messages FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM chats 
      JOIN folders ON folders.id = chats.folder_id
      WHERE chats.id = messages.chat_id 
      AND (
        folders.owner_id = auth.uid() 
        OR EXISTS (
          SELECT 1 FROM folder_shares 
          WHERE folder_shares.folder_id = folders.id 
          AND folder_shares.shared_with_email = (SELECT email FROM auth.users WHERE id = auth.uid())
        )
      )
    )
  );

CREATE POLICY "Users can create messages in accessible chats"
  ON messages FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM chats 
      JOIN folders ON folders.id = chats.folder_id
      WHERE chats.id = messages.chat_id AND folders.owner_id = auth.uid()
    )
  );

-- AI Responses policies
CREATE POLICY "Users can view AI responses for accessible messages"
  ON ai_responses FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM messages
      JOIN chats ON chats.id = messages.chat_id
      JOIN folders ON folders.id = chats.folder_id
      WHERE messages.id = ai_responses.message_id
      AND (
        folders.owner_id = auth.uid() 
        OR EXISTS (
          SELECT 1 FROM folder_shares 
          WHERE folder_shares.folder_id = folders.id 
          AND folder_shares.shared_with_email = (SELECT email FROM auth.users WHERE id = auth.uid())
        )
      )
    )
  );

CREATE POLICY "System can create AI responses"
  ON ai_responses FOR INSERT
  TO authenticated
  WITH CHECK (true);

-- Research Papers policies
CREATE POLICY "Users can view research for accessible messages"
  ON research_papers FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM messages
      JOIN chats ON chats.id = messages.chat_id
      JOIN folders ON folders.id = chats.folder_id
      WHERE messages.id = research_papers.message_id
      AND (
        folders.owner_id = auth.uid() 
        OR EXISTS (
          SELECT 1 FROM folder_shares 
          WHERE folder_shares.folder_id = folders.id 
          AND folder_shares.shared_with_email = (SELECT email FROM auth.users WHERE id = auth.uid())
        )
      )
    )
  );

-- Folder Shares policies
CREATE POLICY "Users can view shares for accessible folders"
  ON folder_shares FOR SELECT
  TO authenticated
  USING (
    EXISTS (SELECT 1 FROM folders WHERE folders.id = folder_shares.folder_id AND folders.owner_id = auth.uid())
    OR shared_with_email = (SELECT email FROM auth.users WHERE id = auth.uid())
  );

CREATE POLICY "Users can share own folders"
  ON folder_shares FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (SELECT 1 FROM folders WHERE folders.id = folder_shares.folder_id AND folders.owner_id = auth.uid())
    AND auth.uid() = shared_by
  );

CREATE POLICY "Users can delete shares for own folders"
  ON folder_shares FOR DELETE
  TO authenticated
  USING (EXISTS (SELECT 1 FROM folders WHERE folders.id = folder_shares.folder_id AND folders.owner_id = auth.uid()));

-- Audit Logs policies
CREATE POLICY "Users can view own audit logs"
  ON audit_logs FOR SELECT
  TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "System can create audit logs"
  ON audit_logs FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_folders_owner ON folders(owner_id);
CREATE INDEX IF NOT EXISTS idx_chats_folder ON chats(folder_id);
CREATE INDEX IF NOT EXISTS idx_chats_parent ON chats(parent_chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_ai_responses_message ON ai_responses(message_id);
CREATE INDEX IF NOT EXISTS idx_research_papers_message ON research_papers(message_id);
CREATE INDEX IF NOT EXISTS idx_folder_shares_folder ON folder_shares(folder_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(user_id);

-- Trigger function for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add triggers
DROP TRIGGER IF EXISTS update_folders_updated_at ON folders;
CREATE TRIGGER update_folders_updated_at
  BEFORE UPDATE ON folders
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_chats_updated_at ON chats;
CREATE TRIGGER update_chats_updated_at
  BEFORE UPDATE ON chats
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();