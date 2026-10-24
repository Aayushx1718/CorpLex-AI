-- Repeatable, additive views. Rank versions before joining one-to-many facts.
BEGIN;
SELECT pg_advisory_xact_lock(42003);
CREATE OR REPLACE VIEW analytics_latest_documents AS
WITH ranked AS (
    SELECT c.id AS contract_id, c.title, c.contract_type, v.id AS document_id,
           v.version_number, v.effective_date, v.expiration_date, v.created_at,
           ROW_NUMBER() OVER (PARTITION BY c.id ORDER BY v.version_number DESC) AS version_rank
    FROM contracts c JOIN document_versions v ON v.contract_id = c.id
    JOIN document_sources s ON s.document_version_id = v.id
    WHERE v.status = 'validated'
)
SELECT contract_id, title, contract_type, document_id, version_number,
       effective_date, expiration_date, created_at
FROM ranked WHERE version_rank = 1;

CREATE OR REPLACE VIEW analytics_obligations AS
SELECT d.contract_id, d.document_id, o.id AS obligation_id, o.clause_id,
       o.kind, o.description, o.amount, o.currency, o.recurrence,
       o.due_date, o.review_status
FROM analytics_latest_documents d JOIN clauses c ON c.document_version_id = d.document_id
JOIN obligations o ON o.clause_id = c.id;

-- Aggregate names independently: party joins must never multiply obligation facts.
CREATE OR REPLACE VIEW analytics_contract_parties AS
SELECT cp.document_version_id AS document_id,
       array_agg(DISTINCT p.legal_name ORDER BY p.legal_name) AS party_names
FROM contract_parties cp JOIN parties p ON p.id = cp.party_id
GROUP BY cp.document_version_id;
COMMIT;
