import json
import re
from typing import TypedDict,Literal
from uuid import UUID,uuid4
from fastapi import APIRouter,HTTPException,Request
from pydantic import BaseModel,Field,model_validator
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from langgraph.graph import StateGraph,START,END
from langsmith import tracing_context
from app.security import require_reviewer
from app.research.retrieval import chunks


class GraphState(TypedDict):
    source:dict
    clauses:list[dict]
    obligations:list[dict]
    report:dict


def make_graph():
    builder=StateGraph(GraphState)
    def extraction(state):
        s=state['source']
        return {'report':{'document_id':str(s['id']),'title':s['title'],'version_number':s['version_number'],
                          'source_sha256':s['sha256'],'trace':['Document Extraction Agent'],
                          'extraction':{'characters':len(s['canonical_text']),'warnings':s['warnings']}}}
    def clause_analysis(state):
        r=state['report'];r['trace'].append('Clause Analysis Agent')
        r['clauses']=[{'id':str(c['id']),'heading':c['heading'],'text':c['text_content'],'char_start':c['char_start'],'char_end':c['char_end']} for c in state['clauses']]
        return {'report':r}
    def risk(state):
        r=state['report'];r['trace'].append('Risk Assessment Agent')
        r['risk']={'validated_risk_model':False,'review_cues':[{'clause_id':str(c['id']),'source_text':c['text_content'],
            'reason':'Rule matched a liability/termination/renewal expression; not a validated risk prediction.'}
            for c in state['clauses'] if re.search(r'liability|terminat|renew|penalt',c['text_content'],re.I)]}
        return {'report':r}
    def financial(state):
        r=state['report'];r['trace'].append('Financial Analysis Agent')
        r['obligation_candidates']=[{k:(str(v) if isinstance(v,(UUID,)) or k=='amount' and v is not None else v) for k,v in row.items()} for row in state['obligations']]
        r['financial_notice']='No exposure/loss total is inferred. Use an explicit scenario with source-linked assumptions.'
        return {'report':r}
    def retrieval(state):
        r=state['report'];r['trace'].append('Retrieval Agent')
        r['retrieval']={'source_chunk_count':sum(len(chunks(c)) for c in state['clauses']),
                        'policy':'Version-scoped source chunks; research answers require exact citations.'}
        return {'report':r}
    def report(state):
        r=state['report'];r['trace'].append('Report Generation Agent')
        r['notice']='Preliminary decision-support report. Not legal advice. No recommendation is authorized by this workflow.'
        r['approval_required']=True
        return {'report':r}
    nodes=[('extraction_agent',extraction),('clause_agent',clause_analysis),('risk_agent',risk),('financial_agent',financial),('retrieval_agent',retrieval),('report_agent',report)]
    previous=START
    for name,fn in nodes:
        builder.add_node(name,fn);builder.add_edge(previous,name);previous=name
    builder.add_edge(previous,END)
    return builder.compile()


class RunRequest(BaseModel):document_id:UUID
class ObligationDecision(BaseModel):
    obligation_id:UUID
    decision:Literal['approved','rejected']
class ReviewRequest(BaseModel):
    decision:Literal['approved','rejected']
    reviewer:str=Field(min_length=2,max_length=100)
    note:str=Field(min_length=10,max_length=1000)
    obligations:list[ObligationDecision]=Field(default_factory=list,max_length=100)

    @model_validator(mode='after')
    def valid(self):
        if not self.reviewer.strip() or len(self.note.strip())<10 or '\x00' in self.reviewer+self.note:
            raise ValueError('Provide a reviewer and meaningful review note.')
        if len({r.obligation_id for r in self.obligations})!=len(self.obligations):raise ValueError('Duplicate obligation decisions.')
        if self.decision=='rejected' and self.obligations:raise ValueError('A rejected report cannot change obligation reviews.')
        return self


def get_run(connection,run_id):
    row=connection.execute(text('SELECT * FROM workflow_runs WHERE id=:id'),{'id':run_id}).mappings().first()
    if not row:raise HTTPException(404,'Workflow run not found.')
    return dict(row)


def build_workflow_router(engine,settings):
    router=APIRouter(prefix='/api/workflows',tags=['review workflows'])
    graph=make_graph()

    @router.post('',status_code=201)
    def create(body:RunRequest):
        try:
            with engine.begin() as connection:
                # Lock the immutable source version to serialize replays.
                source=connection.execute(text('''SELECT v.*,c.title,s.canonical_text,s.warnings FROM document_versions v
                    JOIN contracts c ON c.id=v.contract_id JOIN document_sources s ON s.document_version_id=v.id
                    WHERE v.id=:id FOR UPDATE OF v'''),{'id':body.document_id}).mappings().first()
                if not source:raise HTTPException(404,'Ingested document not found.')
                existing=connection.execute(text('SELECT id FROM workflow_runs WHERE document_version_id=:id'),{'id':body.document_id}).scalar_one_or_none()
                if existing:return get_run(connection,existing)
                clauses=[dict(row) for row in connection.execute(text('SELECT * FROM clauses WHERE document_version_id=:id ORDER BY ordinal'),{'id':body.document_id}).mappings()]
                if len(clauses)>500:raise HTTPException(413,'Workflow review is limited to 500 clauses.')
                for c in clauses:
                    if source['canonical_text'][c['char_start']:c['char_end']]!=c['text_content']:
                        raise HTTPException(409,'Stored source evidence failed validation.')
                obligations=[dict(row) for row in connection.execute(text('''SELECT o.id,o.clause_id,o.kind,o.description,o.amount,o.currency,o.recurrence,o.review_status
                    FROM obligations o JOIN clauses c ON c.id=o.clause_id WHERE c.document_version_id=:id ORDER BY c.ordinal,o.id'''),{'id':body.document_id}).mappings()]
                with tracing_context(enabled=False):
                    report=graph.invoke({'source':dict(source),'clauses':clauses,'obligations':obligations,'report':{}},config={'recursion_limit':20})['report']
                run_id=uuid4()
                connection.execute(text("INSERT INTO workflow_runs(id,document_version_id,state,report) VALUES (:id,:doc,'awaiting_review',CAST(:report AS jsonb))"),{'id':run_id,'doc':body.document_id,'report':json.dumps(report)})
                connection.execute(text("INSERT INTO audit_events(actor_id,action,entity_type,entity_id) VALUES ('local-development','workflow.created','workflow_run',:id)"),{'id':run_id})
                return get_run(connection,run_id)
        except SQLAlchemyError:raise HTTPException(503,'Workflow storage unavailable.') from None

    @router.get('')
    def list_runs():
        try:
            with engine.connect() as connection:
                return {'items':[dict(row) for row in connection.execute(text('SELECT id,document_version_id,state,created_at,reviewer FROM workflow_runs ORDER BY created_at DESC LIMIT 100')).mappings()]}
        except SQLAlchemyError:raise HTTPException(503,'Workflow storage unavailable.') from None

    @router.get('/{run_id}')
    def detail(run_id:UUID):
        try:
            with engine.connect() as connection:return get_run(connection,run_id)
        except SQLAlchemyError:raise HTTPException(503,'Workflow storage unavailable.') from None

    @router.post('/{run_id}/review')
    def review(run_id:UUID,body:ReviewRequest,request:Request):
        require_reviewer(request,settings)
        try:
            with engine.begin() as connection:
                connection.execute(text('SELECT id FROM workflow_runs WHERE id=:id FOR UPDATE'),{'id':run_id})
                run=get_run(connection,run_id)
                if run['state']!='awaiting_review':
                    raise HTTPException(409,'This decision is already recorded; reviews are immutable. Generate a new source version for revised analysis.')
                for item in body.obligations:
                    count=connection.execute(text('''UPDATE obligations SET review_status=:state WHERE id=:obligation
                        AND clause_id IN (SELECT id FROM clauses WHERE document_version_id=:doc)'''),
                        {'state':item.decision,'obligation':item.obligation_id,'doc':run['document_version_id']}).rowcount
                    if count!=1:raise HTTPException(409,'Obligation decision falls outside the reviewed source version.')
                run['report']['human_review']={'decision':body.decision,'reviewer':body.reviewer,'note':body.note,
                    'identity_mode':'token-authorized' if settings.corplex_review_token else 'unverified-local-demo',
                    'obligation_decisions':[{'obligation_id':str(i.obligation_id),'decision':i.decision} for i in body.obligations]}
                connection.execute(text('''UPDATE workflow_runs SET state=:state,reviewed_at=now(),reviewer=:reviewer,review_note=:note,report=CAST(:report AS jsonb) WHERE id=:id'''),
                    {'id':run_id,'state':body.decision,'reviewer':body.reviewer,'note':body.note,'report':json.dumps(run['report'])})
                connection.execute(text('''INSERT INTO audit_events(actor_id,action,entity_type,entity_id,details)
                    VALUES (:actor,:action,'workflow_run',:id,CAST(:details AS jsonb))'''),{'actor':body.reviewer,'action':'workflow.'+body.decision,'id':run_id,
                    'details':json.dumps({'identity_mode':run['report']['human_review']['identity_mode'],'obligation_count':len(body.obligations)})})
                return get_run(connection,run_id)
        except SQLAlchemyError:raise HTTPException(503,'Review could not be saved.') from None

    @router.get('/{run_id}/export')
    def export(run_id:UUID):
        try:
            with engine.connect() as connection:
                run=get_run(connection,run_id)
                if run['state']!='approved':raise HTTPException(409,'Human approval is required before exporting the reviewed report.')
                return {'workflow_id':run_id,'state':'approved','reviewed_at':run['reviewed_at'],'report':run['report']}
        except SQLAlchemyError:raise HTTPException(503,'Workflow storage unavailable.') from None
    return router
