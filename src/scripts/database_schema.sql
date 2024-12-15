-- database_schema.sql

CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    meta_data JSONB,
    embedding VECTOR(1536),  -- Adjust dimension based on your embedder
    document_type TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_documents_embedding ON documents USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_documents_source ON documents USING btree ((meta_data->>'source'));
CREATE INDEX IF NOT EXISTS idx_documents_type ON documents USING btree (document_type);
