BEGIN;
SELECT pg_advisory_xact_lock(42004);
ALTER TABLE research_answers ADD COLUMN IF NOT EXISTS details jsonb NOT NULL DEFAULT '{}'::jsonb;
CREATE TABLE IF NOT EXISTS workflow_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_version_id uuid NOT NULL REFERENCES document_versions(id),
    state text NOT NULL CHECK (state IN ('awaiting_review','approved','rejected')),
    report jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    reviewed_at timestamptz,
    reviewer text,
    review_note text,
    UNIQUE(document_version_id)
);
CREATE INDEX IF NOT EXISTS ix_workflow_state ON workflow_runs(state);
CREATE INDEX IF NOT EXISTS ix_answers_created ON research_answers(created_at);
COMMIT;
