-- Ollive — initial schema
-- Single Postgres holds chats and inference logs (JSONB for forward-compat metadata).

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$ BEGIN
  CREATE TYPE conv_status AS ENUM ('active','cancelled','archived');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE msg_role AS ENUM ('user','assistant','system');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE log_status AS ENUM ('success','error','cancelled','timeout');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS conversations (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title       text,
  status      conv_status NOT NULL DEFAULT 'active',
  provider    text,
  model       text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  metadata    jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_conv_status  ON conversations(status);

CREATE TABLE IF NOT EXISTS messages (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role            msg_role NOT NULL,
  content         text NOT NULL,
  sequence        int NOT NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (conversation_id, sequence)
);
CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id, sequence);

CREATE TABLE IF NOT EXISTS inference_logs (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id   uuid REFERENCES conversations(id) ON DELETE SET NULL,
  message_id        uuid REFERENCES messages(id) ON DELETE SET NULL,
  provider          text NOT NULL,
  model             text NOT NULL,
  status            log_status NOT NULL,
  latency_ms        int,
  ttft_ms           int,
  prompt_tokens     int,
  completion_tokens int,
  total_tokens      int,
  error             text,
  request_preview   text,
  response_preview  text,
  started_at        timestamptz NOT NULL,
  completed_at      timestamptz,
  metadata          jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_log_started        ON inference_logs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_log_model_started  ON inference_logs(model, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_log_status         ON inference_logs(status);
CREATE INDEX IF NOT EXISTS idx_log_conv           ON inference_logs(conversation_id);

CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conv_updated ON conversations;
CREATE TRIGGER trg_conv_updated
  BEFORE UPDATE ON conversations
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
