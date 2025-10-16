-- Migration: Add Knowledge Graph Support
-- Version: 001
-- Description: Adds tables and columns for Knowledge Graph integration
-- Date: 2025-10-15

-- ============================================================================
-- 1. Add KG tracking columns to crawled_content
-- ============================================================================

-- Check if columns exist before adding (SQLite doesn't have ALTER COLUMN IF NOT EXISTS)
-- These will be added by Python migration script with existence checks

-- kg_processed: Flag indicating if KG extraction completed
-- kg_entity_count: Number of entities extracted
-- kg_relationship_count: Number of relationships extracted
-- kg_document_id: Neo4j Document node ID reference
-- kg_processed_at: Timestamp of KG processing completion

-- ============================================================================
-- 2. Create content_chunks table
-- ============================================================================

CREATE TABLE IF NOT EXISTS content_chunks (
    rowid INTEGER PRIMARY KEY,              -- Same as content_vectors rowid
    content_id INTEGER NOT NULL,            -- FK to crawled_content
    chunk_index INTEGER NOT NULL,           -- Sequential: 0, 1, 2, ...
    chunk_text TEXT NOT NULL,               -- Full chunk text
    char_start INTEGER NOT NULL,            -- Position in original markdown
    char_end INTEGER NOT NULL,              -- End position in original markdown
    word_count INTEGER,                     -- Words in chunk
    kg_processed BOOLEAN DEFAULT 0,         -- Flag: KG extraction attempted for this chunk
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (content_id) REFERENCES crawled_content(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_content_chunks_content_id ON content_chunks(content_id);
CREATE INDEX IF NOT EXISTS idx_content_chunks_position ON content_chunks(char_start, char_end);
CREATE INDEX IF NOT EXISTS idx_content_chunks_kg_processed ON content_chunks(kg_processed);

-- ============================================================================
-- 3. Create chunk_entities table
-- ============================================================================

CREATE TABLE IF NOT EXISTS chunk_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_rowid INTEGER NOT NULL,           -- Which chunk (FK to content_chunks)
    content_id INTEGER NOT NULL,            -- Which document (FK to crawled_content)
    entity_text TEXT NOT NULL,              -- "FastAPI", "Python", etc.
    entity_normalized TEXT,                 -- lowercase for deduplication
    entity_type_primary TEXT,               -- "Framework", "Language", etc.
    entity_type_sub1 TEXT,                  -- "Backend", "Interpreted", etc.
    entity_type_sub2 TEXT,                  -- "Python", "DynamicTyped", etc.
    entity_type_sub3 TEXT,                  -- Optional 3rd level
    confidence REAL,                        -- 0.0-1.0 from GLiNER
    offset_start INTEGER,                   -- Position within chunk
    offset_end INTEGER,                     -- End position within chunk
    neo4j_node_id TEXT,                     -- Reference to Neo4j Entity node
    spans_multiple_chunks BOOLEAN DEFAULT 0,  -- True if entity in overlap region
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (chunk_rowid) REFERENCES content_chunks(rowid) ON DELETE CASCADE,
    FOREIGN KEY (content_id) REFERENCES crawled_content(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chunk_entities_chunk ON chunk_entities(chunk_rowid);
CREATE INDEX IF NOT EXISTS idx_chunk_entities_entity ON chunk_entities(entity_text);
CREATE INDEX IF NOT EXISTS idx_chunk_entities_type ON chunk_entities(entity_type_primary, entity_type_sub1);
CREATE INDEX IF NOT EXISTS idx_chunk_entities_content ON chunk_entities(content_id);
CREATE INDEX IF NOT EXISTS idx_chunk_entities_neo4j ON chunk_entities(neo4j_node_id);
CREATE INDEX IF NOT EXISTS idx_chunk_entities_normalized ON chunk_entities(entity_normalized);

-- ============================================================================
-- 4. Create chunk_relationships table
-- ============================================================================

CREATE TABLE IF NOT EXISTS chunk_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id INTEGER NOT NULL,            -- Which document
    subject_entity TEXT NOT NULL,           -- "FastAPI"
    predicate TEXT NOT NULL,                -- "uses", "competes_with", etc.
    object_entity TEXT NOT NULL,            -- "Pydantic"
    confidence REAL,                        -- 0.0-1.0 from vLLM
    context TEXT,                           -- Sentence where relationship found
    neo4j_relationship_id TEXT,             -- Reference to Neo4j relationship
    spans_chunks BOOLEAN DEFAULT 0,         -- True if entities in different chunks
    chunk_rowids TEXT,                      -- JSON array: [45001] or [45001, 45015]
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (content_id) REFERENCES crawled_content(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chunk_relationships_content ON chunk_relationships(content_id);
CREATE INDEX IF NOT EXISTS idx_chunk_relationships_subject ON chunk_relationships(subject_entity);
CREATE INDEX IF NOT EXISTS idx_chunk_relationships_object ON chunk_relationships(object_entity);
CREATE INDEX IF NOT EXISTS idx_chunk_relationships_predicate ON chunk_relationships(predicate);

-- ============================================================================
-- 5. Create kg_processing_queue table
-- ============================================================================

CREATE TABLE IF NOT EXISTS kg_processing_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',          -- pending, processing, completed, failed, skipped
    priority INTEGER DEFAULT 1,             -- Higher = process first
    queued_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    processing_started_at DATETIME,
    processed_at DATETIME,
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    result_summary TEXT,                    -- JSON with statistics
    skipped_reason TEXT,                    -- Reason if status='skipped' (e.g., 'kg_service_unavailable')

    FOREIGN KEY (content_id) REFERENCES crawled_content(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_kg_queue_status ON kg_processing_queue(status, priority, queued_at);
CREATE INDEX IF NOT EXISTS idx_kg_queue_content ON kg_processing_queue(content_id);

-- ============================================================================
-- Migration Complete
-- ============================================================================
