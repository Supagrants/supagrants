CREATE TABLE ai.applications (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    meta_data JSONB,
    embedding VECTOR(768),  -- gemini dim 768, openai dim 1536
    document_type TEXT,
    usage JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    content_hash TEXT,
    filters JSONB DEFAULT '{}'::jsonb
);

-- Recreate indexes
CREATE INDEX IF NOT EXISTS idx_documents_embedding ON ai.documents USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_documents_source ON ai.documents USING btree ((meta_data->>'source'));
CREATE INDEX IF NOT EXISTS idx_documents_type ON ai.documents USING btree (document_type);
CREATE INDEX IF NOT EXISTS idx_documents_content_hash_source ON ai.documents (content_hash, (meta_data->>'source'));