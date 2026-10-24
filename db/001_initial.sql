-- Initial development schema. Applied by scripts/init-db.sh.
-- Changes after initialization require reviewed migrations; do not drop volumes to upgrade.
BEGIN;
CREATE TABLE contracts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title text NOT NULL CHECK (length(trim(title)) > 0),
    contract_type text NOT NULL CHECK (contract_type IN ('nda','employment','vendor','service')),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE document_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id uuid NOT NULL REFERENCES contracts(id),
    version_number integer NOT NULL CHECK (version_number > 0),
    original_filename text NOT NULL,
    storage_key text NOT NULL UNIQUE,
    media_type text NOT NULL CHECK (media_type IN ('application/pdf','application/vnd.openxmlformats-officedocument.wordprocessingml.document')),
    sha256 char(64) NOT NULL UNIQUE CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','processing','validated','failed')),
    effective_date date,
    expiration_date date,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(contract_id, version_number),
    CHECK (expiration_date IS NULL OR effective_date IS NULL OR expiration_date >= effective_date)
);
CREATE TABLE parties (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    legal_name text NOT NULL,
    external_reference text UNIQUE
);
CREATE TABLE contract_parties (
    document_version_id uuid NOT NULL REFERENCES document_versions(id),
    party_id uuid NOT NULL REFERENCES parties(id),
    role text NOT NULL,
    PRIMARY KEY(document_version_id, party_id, role)
);
CREATE TABLE clauses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_version_id uuid NOT NULL REFERENCES document_versions(id),
    ordinal integer NOT NULL CHECK (ordinal > 0),
    heading text,
    text_content text NOT NULL CHECK (length(text_content) > 0),
    page_number integer CHECK (page_number > 0),
    char_start integer NOT NULL CHECK (char_start >= 0),
    char_end integer NOT NULL,
    extractor_version text NOT NULL,
    UNIQUE(document_version_id, ordinal),
    CHECK (char_end > char_start)
);
CREATE TABLE obligations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clause_id uuid NOT NULL REFERENCES clauses(id),
    kind text NOT NULL CHECK (kind IN ('payment','penalty','termination','renewal','notice','other')),
    description text NOT NULL,
    amount numeric(20,4) CHECK (amount >= 0),
    currency char(3) CHECK (currency ~ '^[A-Z]{3}$'),
    due_date date,
    recurrence text,
    review_status text NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','approved','rejected')),
    CHECK ((amount IS NULL) = (currency IS NULL))
);
CREATE TABLE model_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name text NOT NULL,
    model_version text NOT NULL,
    dataset_version text NOT NULL,
    split_manifest_uri text NOT NULL,
    metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
    artifact_uri text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(model_name, model_version, dataset_version)
);
CREATE TABLE clause_annotations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clause_id uuid NOT NULL REFERENCES clauses(id),
    label text NOT NULL,
    rubric_version text NOT NULL,
    annotator_id text NOT NULL,
    rationale text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(clause_id, rubric_version, annotator_id)
);
CREATE TABLE risk_predictions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clause_id uuid NOT NULL REFERENCES clauses(id),
    model_run_id uuid NOT NULL REFERENCES model_runs(id),
    predicted_label text NOT NULL,
    probability numeric(7,6) NOT NULL CHECK (probability BETWEEN 0 AND 1),
    explanation jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(clause_id, model_run_id)
);
CREATE TABLE retrieval_chunks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clause_id uuid NOT NULL REFERENCES clauses(id),
    chunk_number integer NOT NULL CHECK (chunk_number >= 0),
    char_start integer NOT NULL CHECK (char_start >= 0),
    char_end integer NOT NULL CHECK (char_end > char_start),
    text_content text NOT NULL,
    embedding_model text NOT NULL,
    index_version text NOT NULL,
    vector_key text NOT NULL,
    UNIQUE(clause_id, chunk_number, index_version)
);
CREATE TABLE research_answers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    question text NOT NULL,
    answer text NOT NULL,
    model_identifier text NOT NULL,
    prompt_version text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE answer_citations (
    answer_id uuid NOT NULL REFERENCES research_answers(id),
    chunk_id uuid NOT NULL REFERENCES retrieval_chunks(id),
    quoted_text text NOT NULL,
    PRIMARY KEY(answer_id, chunk_id)
);
CREATE TABLE exposure_scenarios (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_version_id uuid NOT NULL REFERENCES document_versions(id),
    name text NOT NULL,
    formula_version text NOT NULL,
    assumptions jsonb NOT NULL,
    result_amount numeric(20,4) NOT NULL CHECK (result_amount >= 0),
    currency char(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE scenario_obligations (
    scenario_id uuid NOT NULL REFERENCES exposure_scenarios(id),
    obligation_id uuid NOT NULL REFERENCES obligations(id),
    PRIMARY KEY(scenario_id, obligation_id)
);
CREATE TABLE audit_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id text NOT NULL,
    action text NOT NULL,
    entity_type text NOT NULL,
    entity_id uuid,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_versions_contract ON document_versions(contract_id);
CREATE INDEX ix_clauses_version ON clauses(document_version_id);
CREATE INDEX ix_obligations_due ON obligations(due_date) WHERE review_status = 'approved';
CREATE INDEX ix_chunks_clause ON retrieval_chunks(clause_id);
COMMIT;
