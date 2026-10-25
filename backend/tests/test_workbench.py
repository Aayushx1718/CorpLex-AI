import pytest
from types import SimpleNamespace
from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.routes import build_router
from app.finance.routes import build_finance_router
from app.finance.comparison import build_comparison_router
from app.workflows.routes import build_workflow_router
from app.security import SecurityMiddleware
from generate_samples import as_docx


@pytest.fixture
def workbench(db_engine):
    app=FastAPI()
    settings=SimpleNamespace(corplex_review_token='review-secret')
    app.include_router(build_router(db_engine));app.include_router(build_finance_router(db_engine))
    app.include_router(build_comparison_router(db_engine));app.include_router(build_workflow_router(db_engine,settings))
    with TestClient(app) as client:yield client


def upload(client,value,**fields):
    r=client.post('/api/contracts',data={'contract_type':'vendor',**fields},files={'file':('demo.docx',as_docx(value),'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
    assert r.status_code==201,r.text
    return r.json()['document']


@pytest.fixture
def payment(workbench):
    return upload(workbench,'SYNTHETIC AGREEMENT\n1. Payment. Buyer shall pay USD 100.1250 per month.\n2. Notice. Either party may terminate with 30 days notice.')


def test_workflow_replay_and_approval_gate(workbench,payment,db_engine):
    run=workbench.post('/api/workflows',json={'document_id':payment['id']})
    assert run.status_code==201,run.text
    run=run.json()
    assert len(run['report']['trace'])==6 and run['state']=='awaiting_review'
    assert workbench.get(f"/api/workflows/{run['id']}/export").status_code==409
    assert workbench.post('/api/workflows',json={'document_id':payment['id']}).json()['id']==run['id']
    obligation=next(o for o in payment['obligations'] if o['amount'] is not None)
    body={'decision':'approved','reviewer':'Test reviewer','note':'Reviewed the extracted terms against source evidence.',
          'obligations':[{'obligation_id':obligation['id'],'decision':'approved'}]}
    assert workbench.post(f"/api/workflows/{run['id']}/review",json=body).status_code==403
    approved=workbench.post(f"/api/workflows/{run['id']}/review",json=body,headers={'X-Review-Token':'review-secret'})
    assert approved.status_code==200,approved.text
    assert approved.json()['state']=='approved'
    assert workbench.get(f"/api/workflows/{run['id']}/export").status_code==200
    assert workbench.post(f"/api/workflows/{run['id']}/review",json=body,headers={'X-Review-Token':'review-secret'}).status_code==409
    with db_engine.connect() as conn:
        assert conn.execute(text('SELECT review_status FROM obligations WHERE id=:id'),{'id':obligation['id']}).scalar_one()=='approved'
        assert conn.execute(text("SELECT count(*) FROM audit_events WHERE action='workflow.created'")).scalar_one()==1


def test_invalid_review_rolls_back(workbench,payment,db_engine):
    run=workbench.post('/api/workflows',json={'document_id':payment['id']}).json()
    valid=payment['obligations'][0]['id']
    body={'decision':'approved','reviewer':'Test reviewer','note':'A review with an out-of-scope obligation.',
          'obligations':[{'obligation_id':valid,'decision':'approved'},{'obligation_id':str(uuid4()),'decision':'approved'}]}
    assert workbench.post(f"/api/workflows/{run['id']}/review",json=body,headers={'X-Review-Token':'review-secret'}).status_code==409
    assert workbench.get(f"/api/workflows/{run['id']}").json()['state']=='awaiting_review'
    with db_engine.connect() as conn:
        assert conn.execute(text('SELECT review_status FROM obligations WHERE id=:id'),{'id':valid}).scalar_one()=='pending'


def test_scenario_exact_formula_pending_ack_and_persistence(workbench,payment):
    obligation=next(o for o in payment['obligations'] if o['amount'] is not None)
    body={'document_id':payment['id'],'name':'Three month what-if','currency':'USD',
          'lines':[{'obligation_id':obligation['id'],'quantity':'3','cap':'250','assumption_note':'Assume three monthly charges and a hypothetical cap.'}]}
    assert workbench.post('/api/finance/scenarios',json=body).status_code==409
    body['include_unreviewed']=True
    result=workbench.post('/api/finance/scenarios',json=body)
    assert result.status_code==201,result.text
    scenario=result.json()
    assert scenario['amount']=='250.0000' and scenario['lines'][0]['uncapped_amount']=='300.3750'
    assert scenario['hypothetical'] is True
    assert workbench.get('/api/finance/scenarios/'+scenario['id']).json()['amount']=='250.0000'
    body['currency']='EUR'
    assert workbench.post('/api/finance/scenarios',json=body).status_code==422
    body['currency']='USD';body['lines']*=2
    assert workbench.post('/api/finance/scenarios',json=body).status_code==422


def test_scenario_ambiguous_terms_require_explicit_assumption(workbench):
    doc=upload(workbench,'1. Delay. A credit of USD 10.00 per day applies, capped at USD 100.00.')
    body={'document_id':doc['id'],'name':'Delay scenario','currency':'USD','include_unreviewed':True,
          'lines':[{'obligation_id':doc['obligations'][0]['id'],'quantity':'4','assumption_note':'Assume four days delay for demonstration only.'}]}
    assert workbench.post('/api/finance/scenarios',json=body).status_code==422
    body['lines'][0].update(assumed_rate='10',cap='100')
    r=workbench.post('/api/finance/scenarios',json=body)
    assert r.status_code==201,r.text
    assert r.json()['amount']=='40.0000' and r.json()['lines'][0]['rate_origin']=='user_assumption'


def test_version_diff_and_unrelated_comparison(workbench,payment):
    new=upload(workbench,'SYNTHETIC AGREEMENT\n1. Payment. Buyer shall pay USD 200.00 per month.\n2. Notice. Either party may terminate with 30 days notice.',contract_id=payment['contract_id'])
    r=workbench.post('/api/comparison',json={'left_document_id':payment['id'],'right_document_id':new['id']})
    assert r.status_code==200,r.text
    result=r.json()
    assert result['same_contract'] is True
    assert any(p['status']=='modified' for p in result['pairs'])
    assert '100.1250' in result['diff'] and '200.00' in result['diff']
    assert workbench.post('/api/comparison',json={'left_document_id':payment['id'],'right_document_id':payment['id']}).status_code==422
    assert workbench.post('/api/comparison',json={'left_document_id':payment['id'],'right_document_id':str(uuid4())}).status_code==404


def test_access_control_and_origin_rejection():
    app=FastAPI()
    @app.get('/api/private')
    def private():return {'ok':True}
    @app.post('/api/write')
    def write():return {'ok':True}
    settings=SimpleNamespace(corplex_access_token='workspace-secret',cors_origins=['http://localhost:5173'])
    app.add_middleware(SecurityMiddleware,settings=settings)
    with TestClient(app) as client:
        assert client.get('/api/private').status_code==401
        assert client.get('/api/private',headers={'Authorization':'Bearer workspace-secret'}).status_code==200
        assert client.post('/api/write',headers={'Authorization':'Bearer workspace-secret','Origin':'https://evil.example'}).status_code==403


def test_production_configuration_refuses_defaults():
    from app.config import Settings
    from pydantic import ValidationError
    with pytest.raises(ValidationError):Settings(app_env='production',_env_file=None)
    secure=Settings(app_env='production',database_url='postgresql+psycopg://demo:nondefault@db/demo',
                    corplex_access_token='a'*40,corplex_review_token='b'*40,_env_file=None)
    assert secure.app_env=='production'
