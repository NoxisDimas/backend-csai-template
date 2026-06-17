Backend Database Schema

AI Customer Service for Shopify Store (Single-Instance)

This document defines the relational database (PostgreSQL) schema used by the backend system. Since this system does not use a Multi-Tenant SaaS model (one instance = one store), the schema is designed to be simple yet robust, with support for pgvector (Knowledge Base) and built-in integration with the LangGraph Checkpointer.

1. System Configuration & Persona

These tables store the store environment settings and parameters for the AI agent's System Prompt.

-- Stores external API keys and operational hours
CREATE TABLE system_configs (
id SERIAL PRIMARY KEY,
shopify_domain VARCHAR(255) NOT NULL,
admin_api_token TEXT NOT NULL,
storefront_api_token TEXT,
webhook_secret VARCHAR(255),
telegram_bot_token VARCHAR(255) NOT NULL,
telegram_chat_id VARCHAR(50) NOT NULL,
operational_hours_json JSONB DEFAULT '{"monday": {"start": "08:00", "end": "17:00"}}',
created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- AI Guardrail & Personality Settings
CREATE TABLE persona_settings (
id SERIAL PRIMARY KEY,
persona_name VARCHAR(100) NOT NULL,
tone_of_voice VARCHAR(100) NOT NULL,
rules TEXT,
out_of_context_message TEXT NOT NULL DEFAULT 'Sorry, I am the AI assistant for this store, assigned only to answer questions within the store''s context.',
created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

2. Dashboard Users (Auth)

-- Dashboard Users (Role: Admin / Staff)
CREATE TABLE users (
id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
name VARCHAR(150) NOT NULL,
email VARCHAR(255) UNIQUE NOT NULL,
role VARCHAR(50) NOT NULL CHECK (role IN ('admin', 'staff')),
password_hash VARCHAR(255) NOT NULL,
created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

3. Conversation Operations & Handoff (Core)

These tables are the heart of the application. conversations.id will be used directly as the thread_id within the LangGraph Checkpointer.

-- Parent thread for customer chat
CREATE TABLE conversations (
id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- Mapped as thread_id in LangGraph
anonymous_customer_id VARCHAR(100) NOT NULL,
status VARCHAR(50) DEFAULT 'active_ai' CHECK (status IN ('active_ai', 'waiting_human', 'human_handling')),
intent VARCHAR(100),
assigned_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
last_activity_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
total_token INT DEFAULT 0,
total_cost NUMERIC(10, 4) DEFAULT 0.0000
);

-- Chat history (Can be synchronized from LangGraph state or written manually)
CREATE TABLE messages (
id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
sender_type VARCHAR(50) NOT NULL CHECK (sender_type IN ('customer', 'ai', 'staff')),
content TEXT NOT NULL,
token_usage INT DEFAULT 0, -- Input+output tokens if sender_type = 'ai'
cost NUMERIC(10, 4) DEFAULT 0.0000, -- Actual cost recorded from OpenRouter
created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Escalation queue tickets
CREATE TABLE tickets (
id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
category VARCHAR(100),
priority VARCHAR(50) DEFAULT 'medium',
status VARCHAR(50) DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved')),
assigned_user_id UUID REFERENCES users(id),
notes TEXT,
created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
resolved_at TIMESTAMP WITH TIME ZONE
);

4. Analytics & Metrics Dashboard

Tables to store the aggregation results of backend cron jobs and Customer Satisfaction ratings. (Note: token usage and cost are calculated dynamically by aggregating `total_token` and `total_cost` directly from the `conversations` table, ensuring exact precision).

-- CSAT rating per conversation
CREATE TABLE feedback (
id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
rating INT NOT NULL CHECK (rating >= 1 AND rating <= 5),
feedback_text TEXT,
created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Daily snapshot of aggregated metrics for the Dashboard
CREATE TABLE metric_snapshots (
id SERIAL PRIMARY KEY,
snapshot_date DATE UNIQUE NOT NULL DEFAULT CURRENT_DATE,
total_tokens INT DEFAULT 0,
estimated_cost NUMERIC(10, 4) DEFAULT 0.0000,
peak_hours_json JSONB,
csat_average NUMERIC(3, 2) DEFAULT 0.00,
total_conversations INT DEFAULT 0,
total_tickets INT DEFAULT 0,
created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

5. Knowledge Base (RAG)

These tables require the installation and activation of the pgvector extension in PostgreSQL (CREATE EXTENSION vector;).

-- Master Knowledge Base documents
CREATE TABLE knowledge_base_documents (
id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
title VARCHAR(255) NOT NULL,
content TEXT NOT NULL,
embedding_status VARCHAR(50) DEFAULT 'pending' CHECK (embedding_status IN ('pending', 'processing', 'completed', 'failed')),
created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Text chunks from splitting and their Embedding Vectors
CREATE TABLE knowledge_base_chunks (
id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
document_id UUID REFERENCES knowledge_base_documents(id) ON DELETE CASCADE,
chunk_text TEXT NOT NULL,
embedding_vector vector(1536), -- Assuming the use of the OpenAI text-embedding-3-small model (1536 dimensions)
chunk_index INT NOT NULL
);

-- Create an HNSW index to speed up Cosine Similarity search
CREATE INDEX ON knowledge_base_chunks USING hnsw (embedding_vector vector_cosine_ops);

6. Observability & Logs

Table to record silent errors that will later be broadcasted to Telegram.

-- Error logging without raw stack traces to the frontend
CREATE TABLE error_logs (
id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
severity VARCHAR(50) NOT NULL CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL')),
category VARCHAR(100) NOT NULL,
workflow_step VARCHAR(150),
error_message TEXT NOT NULL,
conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
telegram_sent_status BOOLEAN DEFAULT FALSE,
created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

7. Special Note: LangGraph Checkpointer

As the backend architecture, we use LangGraph's built-in memory persistence feature.

The backend DOES NOT need to manually create tables to store message history for the agent.

The backend will call AsyncPostgresSaver.create_tables(conn).

LangGraph will automatically initialize its internal tables (checkpoints, checkpoint_blobs, checkpoint_writes) in this database.

As a bridge (mapping), we use conversations.id (UUID type) as the thread_id parameter when executing the create_react_agent.
