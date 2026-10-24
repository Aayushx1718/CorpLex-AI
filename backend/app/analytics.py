"""Read-only portfolio analytics. No FX conversion or loss/exposure estimation."""
from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

# Contract and obligation populations share identical filter predicates. A contract
# without matching obligations stays visible only when no obligation filter is set.
SCOPE = '''
WITH scoped AS (
    SELECT d.* FROM analytics_latest_documents d
    WHERE (CAST(:contract_type AS text) IS NULL OR d.contract_type = :contract_type)
      AND ((CAST(:currency AS text) IS NULL AND CAST(:review_status AS text) IS NULL)
           OR EXISTS (
               SELECT 1 FROM analytics_obligations o WHERE o.contract_id = d.contract_id
               AND (CAST(:currency AS text) IS NULL OR o.currency = :currency)
               AND (CAST(:review_status AS text) IS NULL OR o.review_status = :review_status)
           ))
), facts AS (
    SELECT o.* FROM analytics_obligations o JOIN scoped d ON d.contract_id = o.contract_id
    WHERE (CAST(:currency AS text) IS NULL OR o.currency = :currency)
      AND (CAST(:review_status AS text) IS NULL OR o.review_status = :review_status)
)
'''


def portfolio(engine, params: dict) -> dict:
    def rows(connection, sql):
        return [dict(row) for row in connection.execute(text(SCOPE + sql), params).mappings()]

    # All panels describe one database snapshot, even during concurrent ingestion.
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
        with connection.begin():
            kpis = rows(connection, '''
                SELECT (SELECT count(*) FROM scoped) AS contracts,
                       (SELECT count(*) FROM facts) AS obligations,
                       (SELECT count(*) FROM facts WHERE review_status = 'pending') AS pending_review,
                       (SELECT count(*) FROM scoped WHERE expiration_date IS NULL) AS missing_expiration,
                       (SELECT count(*) FROM scoped WHERE expiration_date BETWEEN :as_of AND :through) AS expiring,
                       (SELECT count(*) FROM facts WHERE due_date < :as_of AND review_status <> 'rejected') AS past_due_dates,
                       (SELECT count(*) FROM facts WHERE due_date IS NULL) AS missing_due_dates
            ''')[0]
            by_type = rows(connection, 'SELECT contract_type, count(*) AS count FROM scoped GROUP BY contract_type ORDER BY contract_type')
            by_kind = rows(connection, 'SELECT kind, review_status, count(*) AS count FROM facts GROUP BY kind, review_status ORDER BY kind, review_status')
            amounts = rows(connection, '''
                SELECT currency, kind, review_status, recurrence, count(*) AS count, sum(amount) AS amount
                FROM facts WHERE amount IS NOT NULL
                GROUP BY currency, kind, review_status, recurrence
                ORDER BY currency, kind, review_status, recurrence NULLS FIRST
            ''')
            for row in amounts:
                row['amount'] = str(row['amount'])  # exact numeric, never JSON floating point
            contracts = rows(connection, '''
                , counts AS (
                    SELECT contract_id, count(*) AS obligations,
                           count(*) FILTER (WHERE review_status = 'pending') AS pending_review
                    FROM facts GROUP BY contract_id
                )
                SELECT d.*, COALESCE(p.party_names, ARRAY[]::text[]) AS party_names,
                       COALESCE(c.obligations, 0) AS obligations, COALESCE(c.pending_review, 0) AS pending_review
                FROM scoped d LEFT JOIN counts c ON c.contract_id = d.contract_id
                LEFT JOIN analytics_contract_parties p ON p.document_id = d.document_id
                ORDER BY d.title, d.contract_id LIMIT :limit OFFSET :offset
            ''')
            deadline_sql = '''
                , events AS (
                    SELECT d.contract_id, d.document_id, d.title, d.contract_type,
                           d.expiration_date AS event_date, 'expiration' AS event_type,
                           CAST(NULL AS uuid) AS clause_id, CAST(NULL AS text) AS review_status,
                           'Recorded contract expiration; renewal notice deadline is not inferred.' AS description
                    FROM scoped d WHERE d.expiration_date BETWEEN :as_of AND :through
                    UNION ALL
                    SELECT d.contract_id, d.document_id, d.title, d.contract_type,
                           f.due_date, f.kind || '_due', f.clause_id, f.review_status, f.description
                    FROM facts f JOIN scoped d ON d.contract_id = f.contract_id
                    WHERE f.due_date <= :through AND f.review_status <> 'rejected'
                )
            '''
            deadline_total = rows(connection, deadline_sql + 'SELECT count(*) AS count FROM events')[0]['count']
            deadlines = rows(connection, deadline_sql + '''
                SELECT * FROM events ORDER BY event_date, contract_id, event_type, clause_id NULLS FIRST LIMIT 100
            ''')
    return {'as_of': params['as_of'], 'through': params['through'],
            'filters': {k: params[k] for k in ['contract_type', 'currency', 'review_status']},
            'kpis': kpis, 'by_type': by_type, 'by_kind': by_kind, 'amount_groups': amounts,
            'contracts': contracts, 'limit': params['limit'], 'offset': params['offset'],
            'deadlines': deadlines, 'deadline_total': deadline_total}


def build_analytics_router(engine):
    router = APIRouter(prefix='/api/analytics', tags=['analytics'])

    @router.get('/overview')
    def overview(
        contract_type: Literal['nda', 'employment', 'vendor', 'service'] | None = None,
        currency: Annotated[str | None, Query(pattern='^[A-Z]{3}$')] = None,
        review_status: Literal['pending', 'approved', 'rejected'] | None = None,
        as_of: date | None = None,
        horizon_days: Annotated[int, Query(ge=1, le=365)] = 90,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
    ):
        # Explicit, reproducible date window. Server default is the UTC calendar date.
        from datetime import datetime, timezone
        reference = as_of or datetime.now(timezone.utc).date()
        if reference > date(9998, 12, 31):
            raise HTTPException(422, 'As-of date exceeds the supported range.')
        try:
            return portfolio(engine, {'contract_type': contract_type, 'currency': currency,
                                     'review_status': review_status, 'as_of': reference,
                                     'through': reference + timedelta(days=horizon_days),
                                     'limit': limit, 'offset': offset})
        except SQLAlchemyError:
            raise HTTPException(503, 'Analytics unavailable. Check database connectivity and migrations.') from None

    return router
