from typing import Literal
from threading import BoundedSemaphore
from uuid import UUID
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError
from app.research.service import answer_question


class ResearchRequest(BaseModel):
    question: str = Field(min_length=5, max_length=1000)
    document_ids: list[UUID] = Field(default_factory=list, max_length=10)
    contract_type: Literal['nda','employment','vendor','service'] | None = None
    retrieval_mode: Literal['lexical','dense','hybrid'] = 'hybrid'
    answer_mode: Literal['local','hosted'] = 'local'

    @field_validator('question')
    @classmethod
    def clean(cls, value):
        if not value.strip() or '\x00' in value:
            raise ValueError('A nonempty question without null characters is required.')
        return value.strip()


def build_research_router(engine, settings):
    router = APIRouter(prefix='/api/research', tags=['contract research'])
    slots = BoundedSemaphore(2)

    @router.get('/status')
    def status():
        return {'local_available': True, 'hosted_configured': bool(settings.corplex_llm_api_key),
                'hosted_model': settings.corplex_llm_model, 'embedding_model': 'corpus-local-lsa-v1',
                'answer_policy': 'Validated exact quotations only. No free-form legal claims.'}

    @router.post('/ask')
    def ask(body: ResearchRequest):
        if not slots.acquire(blocking=False):
            raise HTTPException(429, 'Research capacity is busy; retry shortly.')
        try:
            return answer_question(engine, body, settings)
        except SQLAlchemyError:
            raise HTTPException(503, 'Research storage unavailable. Check migrations and database connectivity.') from None
        finally:
            slots.release()
    return router
