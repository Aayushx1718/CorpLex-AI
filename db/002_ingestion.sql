-- Additive, repeatable Phase 2 migration; preserves existing contracts.
BEGIN;
SELECT pg_advisory_xact_lock(42002);
CREATE TABLE IF NOT EXISTS document_sources (
    document_version_id uuid PRIMARY KEY REFERENCES document_versions(id),
    original_content bytea NOT NULL CHECK (octet_length(original_content) BETWEEN 1 AND 10485760),
    canonical_text text NOT NULL CHECK (length(canonical_text) > 0),
    source_units jsonb NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
    extractor_version text NOT NULL
);
CREATE TABLE IF NOT EXISTS document_entities (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_version_id uuid NOT NULL REFERENCES document_versions(id),
    kind text NOT NULL CHECK (kind IN ('party','date','money')),
    raw_text text NOT NULL,
    normalized_value text NOT NULL,
    currency char(3),
    char_start integer NOT NULL CHECK (char_start >= 0),
    char_end integer NOT NULL CHECK (char_end > char_start),
    CHECK ((kind = 'money') = (currency IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS ix_entities_document ON document_entities(document_version_id);
COMMIT;
