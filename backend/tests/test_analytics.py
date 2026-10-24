from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
import pytest
from app.analytics import build_analytics_router


@pytest.fixture
def analytics_client(db_engine):
    app = FastAPI()
    app.include_router(build_analytics_router(db_engine))
    with TestClient(app) as client:
        yield client


def add_document(conn, title, kind, expiration=None, contract=None, version=1):
    contract = contract or uuid4()
    if version == 1:
        conn.execute(text('INSERT INTO contracts(id,title,contract_type) VALUES (:id,:title,:kind)'), {'id': contract, 'title': title, 'kind': kind})
    doc = uuid4()
    conn.execute(text('''INSERT INTO document_versions(id,contract_id,version_number,original_filename,storage_key,media_type,sha256,status,expiration_date)
                        VALUES (:id,:contract,:version,'fixture.pdf',:key,'application/pdf',:sha,'validated',:expiration)'''),
                 {'id': doc, 'contract': contract, 'version': version, 'key': str(doc), 'sha': uuid4().hex * 2, 'expiration': expiration})
    conn.execute(text('''INSERT INTO document_sources(document_version_id,original_content,canonical_text,source_units,extractor_version)
                        VALUES (:id,:bytes,'Fixture source','[]','test')'''), {'id': doc, 'bytes': b'fixture'})
    return contract, doc


def add_obligation(conn, doc, amount, currency, kind='payment', recurrence=None, state='pending', due=None):
    clause = uuid4()
    ordinal = conn.execute(text('SELECT count(*) + 1 FROM clauses WHERE document_version_id=:id'), {'id': doc}).scalar_one()
    conn.execute(text('''INSERT INTO clauses(id,document_version_id,ordinal,text_content,char_start,char_end,extractor_version)
                        VALUES (:id,:doc,:ordinal,'Fixture source',0,14,'test')'''), {'id': clause, 'doc': doc, 'ordinal': ordinal})
    conn.execute(text('''INSERT INTO obligations(clause_id,kind,description,amount,currency,recurrence,review_status,due_date)
                        VALUES (:clause,:kind,'Fixture source',:amount,:currency,:recurrence,:state,:due)'''),
                 {'clause': clause, 'kind': kind, 'amount': amount, 'currency': currency, 'recurrence': recurrence, 'state': state, 'due': due})


@pytest.fixture
def portfolio_fixture(db_engine):
    with db_engine.begin() as conn:
        vendor, old = add_document(conn, 'Vendor example', 'vendor', '2026-03-15')
        add_obligation(conn, old, '9999', 'USD')
        _, current = add_document(conn, 'Vendor example', 'vendor', '2026-04-01', vendor, 2)
        add_obligation(conn, current, '100', 'USD', recurrence='monthly')
        add_obligation(conn, current, '20', 'USD', due='2026-02-01')
        add_obligation(conn, current, '30', 'EUR', kind='penalty')
        add_obligation(conn, current, '999', 'USD', state='rejected', due='2026-01-01')
        for name in ['Buyer Example', 'Supplier Example']:
            party = uuid4()
            conn.execute(text('INSERT INTO parties(id,legal_name) VALUES (:id,:name)'), {'id': party, 'name': name})
            conn.execute(text("INSERT INTO contract_parties(document_version_id,party_id,role) VALUES (:doc,:party,'unspecified')"), {'doc': current, 'party': party})
        _, employment = add_document(conn, 'Employment example', 'employment')
        add_obligation(conn, employment, '200', 'USD', recurrence='monthly')
        add_document(conn, 'NDA example', 'nda')
        _, service = add_document(conn, 'Service example', 'service', '2027-01-01')
        add_obligation(conn, service, '50', 'GBP', state='approved', due='2026-03-10')
    return vendor


def overview(client, **params):
    response = client.get('/api/analytics/overview', params={'as_of': '2026-03-01', **params})
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_portfolio(analytics_client):
    data = overview(analytics_client)
    assert set(data['kpis'].values()) == {0}
    assert data['amount_groups'] == data['contracts'] == data['deadlines'] == []


def test_kpis_latest_version_and_no_party_join_multiplication(analytics_client, portfolio_fixture):
    data = overview(analytics_client)
    assert data['kpis'] == {'contracts': 4, 'obligations': 6, 'pending_review': 4, 'missing_expiration': 2,
                            'expiring': 1, 'past_due_dates': 1, 'missing_due_dates': 3}
    vendor = next(c for c in data['contracts'] if c['contract_type'] == 'vendor')
    assert vendor['version_number'] == 2
    assert vendor['obligations'] == 4
    assert vendor['party_names'] == ['Buyer Example', 'Supplier Example']
    assert sum(t['count'] for t in data['by_type']) == 4
    assert sum(t['count'] for t in data['by_kind']) == 6
    monthly = next(a for a in data['amount_groups'] if a['currency'] == 'USD' and a['recurrence'] == 'monthly')
    assert monthly['amount'] == '300.0000'  # 100 + 200; not 9999 + 100 + 200; not multiplied by parties
    assert monthly['count'] == 2
    assert len(data['amount_groups']) == 5  # EUR/GBP, monthly/unspecified and rejected separated


def test_consistent_currency_and_review_filters(analytics_client, portfolio_fixture):
    data = overview(analytics_client, currency='USD', review_status='pending')
    assert data['kpis']['contracts'] == 2
    assert data['kpis']['obligations'] == 3
    assert {c['contract_type'] for c in data['contracts']} == {'vendor', 'employment'}
    assert all(a['currency'] == 'USD' and a['review_status'] == 'pending' for a in data['amount_groups'])
    euro = overview(analytics_client, currency='EUR')
    assert euro['kpis']['contracts'] == euro['kpis']['obligations'] == 1
    assert euro['amount_groups'][0]['amount'] == '30.0000'
    assert overview(analytics_client, currency='JPY')['kpis']['contracts'] == 0
    nda = overview(analytics_client, contract_type='nda')
    assert nda['kpis']['contracts'] == 1 and nda['kpis']['obligations'] == 0
    assert overview(analytics_client, contract_type='nda', review_status='pending')['kpis']['contracts'] == 0


def test_deadlines_window_missing_dates_and_rejected_exclusion(analytics_client, portfolio_fixture):
    data = overview(analytics_client)
    assert data['deadline_total'] == 3  # pending past due, approved future due, vendor expiration
    assert [d['event_date'] for d in data['deadlines']] == ['2026-02-01', '2026-03-10', '2026-04-01']
    assert not any(d['review_status'] == 'rejected' for d in data['deadlines'])
    assert overview(analytics_client, horizon_days=1)['deadline_total'] == 1
    boundary = overview(analytics_client, as_of='2026-04-01', horizon_days=1)
    assert boundary['kpis']['expiring'] == 1


def test_pagination_does_not_change_aggregate_totals(analytics_client, portfolio_fixture):
    data = overview(analytics_client, limit=1, offset=1)
    assert data['kpis']['contracts'] == 4
    assert len(data['contracts']) == 1
    assert data['contracts'][0]['title'] == 'NDA example'
    assert overview(analytics_client, offset=100)['contracts'] == []


@pytest.mark.parametrize('params', [{'currency': 'usd'}, {'currency': "USD' OR 1=1"}, {'contract_type': 'unknown'},
                                    {'review_status': 'unknown'}, {'horizon_days': 366}, {'as_of': 'not-a-date'},
                                    {'as_of': '9999-12-31'}, {'limit': 0}])
def test_invalid_filters_are_rejected(analytics_client, params):
    assert analytics_client.get('/api/analytics/overview', params=params).status_code == 422


def test_exact_numeric_amounts_do_not_round(analytics_client, db_engine):
    with db_engine.begin() as conn:
        _, doc = add_document(conn, 'Precision fixture', 'vendor')
        add_obligation(conn, doc, '9007199254740993.1234', 'USD')
    data = overview(analytics_client)
    assert data['amount_groups'][0]['amount'] == '9007199254740993.1234'


def test_missing_migration_returns_sanitized_503(analytics_client, db_engine):
    with db_engine.begin() as conn:
        conn.execute(text('DROP VIEW analytics_latest_documents CASCADE'))
    response = analytics_client.get('/api/analytics/overview')
    assert response.status_code == 503
    assert response.json() == {'detail': 'Analytics unavailable. Check database connectivity and migrations.'}


def test_deadline_truncation_is_explicit(analytics_client, db_engine):
    with db_engine.begin() as conn:
        _, doc = add_document(conn, 'Many dates', 'service')
        for _ in range(101):
            add_obligation(conn, doc, None, None, due='2026-03-02')
    data = overview(analytics_client)
    assert data['deadline_total'] == 101
    assert len(data['deadlines']) == 100
