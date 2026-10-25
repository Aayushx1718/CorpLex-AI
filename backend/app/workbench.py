from fastapi import APIRouter,HTTPException,Query
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


def build_workbench_router(engine):
    router=APIRouter(prefix='/api/workbench',tags=['workbench metadata'])
    @router.get('/documents')
    def documents():
        try:
            with engine.connect() as conn:
                rows=[dict(r) for r in conn.execute(text('''SELECT v.id,c.title,c.contract_type,v.version_number,v.created_at
                    FROM document_versions v JOIN contracts c ON c.id=v.contract_id JOIN document_sources s ON s.document_version_id=v.id
                    ORDER BY v.created_at DESC,v.id LIMIT 200''')).mappings()]
                count=conn.execute(text('SELECT count(*) FROM document_sources')).scalar_one()
                return {'items':rows,'total':count,'limit':200}
        except SQLAlchemyError:raise HTTPException(503,'Document choices unavailable.') from None
    @router.get('/audit')
    def audit(limit:int=Query(default=50,ge=1,le=100),offset:int=Query(default=0,ge=0)):
        try:
            with engine.connect() as conn:
                return {'items':[dict(r) for r in conn.execute(text('''SELECT id::text AS id,actor_id,action,entity_type,entity_id,created_at,details
                    FROM audit_events ORDER BY created_at DESC,id DESC LIMIT :limit OFFSET :offset'''),{'limit':limit,'offset':offset}).mappings()],
                    'limit':limit,'offset':offset}
        except SQLAlchemyError:raise HTTPException(503,'Audit log unavailable.') from None
    return router
