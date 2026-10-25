-- Fail on damaged original bytes, absent source records or invalid source offsets.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM document_versions v LEFT JOIN document_sources s ON s.document_version_id=v.id
    WHERE v.status='validated' AND (s.document_version_id IS NULL OR encode(sha256(s.original_content),'hex') <> trim(v.sha256))
  ) THEN RAISE EXCEPTION 'Original document integrity check failed'; END IF;
  IF EXISTS (
    SELECT 1 FROM clauses c JOIN document_sources s ON s.document_version_id=c.document_version_id
    WHERE c.char_start < 0 OR c.char_end > length(s.canonical_text)
      OR substring(s.canonical_text FROM c.char_start+1 FOR c.char_end-c.char_start) <> c.text_content
  ) THEN RAISE EXCEPTION 'Clause source offsets failed'; END IF;
  IF EXISTS (
    SELECT 1 FROM document_entities e JOIN document_sources s ON s.document_version_id=e.document_version_id
    WHERE e.char_start < 0 OR e.char_end > length(s.canonical_text)
      OR substring(s.canonical_text FROM e.char_start+1 FOR e.char_end-e.char_start) <> e.raw_text
  ) THEN RAISE EXCEPTION 'Entity source offsets failed'; END IF;
  IF EXISTS (
    SELECT 1 FROM document_sources s CROSS JOIN LATERAL jsonb_array_elements(s.source_units) u
    WHERE NOT (u ? 'char_start' AND u ? 'char_end') OR (u->>'char_start') IS NULL OR (u->>'char_end') IS NULL
      OR (u->>'char_start')::integer < 0 OR (u->>'char_end')::integer > length(s.canonical_text)
      OR (u->>'char_end')::integer < (u->>'char_start')::integer
  ) THEN RAISE EXCEPTION 'Source unit offsets failed'; END IF;
  PERFORM document_id FROM analytics_latest_documents LIMIT 1;
END $$;
-- Counts reveal inventory, not confidential document text.
SELECT 'contracts' AS object, count(*) FROM contracts
UNION ALL SELECT 'document_versions', count(*) FROM document_versions
UNION ALL SELECT 'document_sources', count(*) FROM document_sources
UNION ALL SELECT 'clauses', count(*) FROM clauses
UNION ALL SELECT 'obligations', count(*) FROM obligations
UNION ALL SELECT 'research_answers', count(*) FROM research_answers
UNION ALL SELECT 'exposure_scenarios', count(*) FROM exposure_scenarios
UNION ALL SELECT 'workflow_runs', count(*) FROM workflow_runs
UNION ALL SELECT 'audit_events', count(*) FROM audit_events;
