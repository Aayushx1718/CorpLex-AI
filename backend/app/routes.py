from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.extraction import ExtractionError, MAX_FILE_BYTES
from app.ingestion import document_detail, ingest
from app.parser import ParserBusy


def build_router(engine):
    router = APIRouter(prefix='/api', tags=['contracts'])

    @router.post('/contracts', status_code=201)
    def upload_contract(
        file: Annotated[UploadFile, File()],
        contract_type: Annotated[Literal['nda', 'employment', 'vendor', 'service'], Form()],
        title: Annotated[str | None, Form(max_length=200)] = None,
        contract_id: Annotated[UUID | None, Form()] = None,
    ):
        filename = (file.filename or '').replace('\\', '/').rsplit('/', 1)[-1].strip()
        if not filename or len(filename) > 200 or '\x00' in filename:
            raise HTTPException(422, 'A valid filename of at most 200 characters is required.')
        if title is not None and (not title.strip() or '\x00' in title):
            raise HTTPException(422, 'Title must be non-empty text without null characters.')
        data = file.file.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(413, 'File exceeds 10 MiB.')
        try:
            document, duplicate = ingest(engine, data, filename, file.content_type,
                                         contract_type, title.strip() if title else None, contract_id)
        except ParserBusy:
            raise HTTPException(503, 'Parser is busy. Retry shortly.') from None
        except ExtractionError as exc:
            raise HTTPException(422, str(exc)) from None
        except SQLAlchemyError:
            raise HTTPException(503, 'Ingestion could not be persisted. Retry when the database is available.') from None
        finally:
            file.file.close()
        return JSONResponse(jsonable_encoder({'duplicate': duplicate, 'document': document}),
                            status_code=200 if duplicate else 201)

    @router.get('/contracts')
    def list_contracts(limit: Annotated[int, Query(ge=1, le=100)] = 25,
                       offset: Annotated[int, Query(ge=0)] = 0):
        try:
            with engine.connect() as connection:
                rows = connection.execute(text('''
                    SELECT c.id AS contract_id, c.title, c.contract_type,
                           v.id AS document_id, v.version_number, v.original_filename, v.created_at
                    FROM contracts c
                    JOIN LATERAL (
                        SELECT * FROM document_versions dv WHERE dv.contract_id = c.id
                        AND EXISTS (SELECT 1 FROM document_sources s WHERE s.document_version_id = dv.id)
                        ORDER BY version_number DESC LIMIT 1
                    ) v ON true
                    ORDER BY v.created_at DESC, c.id LIMIT :limit OFFSET :offset
                '''), {'limit': limit, 'offset': offset}).mappings()
                return {'items': [dict(row) for row in rows], 'limit': limit, 'offset': offset}
        except SQLAlchemyError:
            raise HTTPException(503, 'Contract repository unavailable.') from None

    @router.get('/documents/{document_id}')
    def get_document(document_id: UUID):
        try:
            with engine.connect() as connection:
                return document_detail(connection, document_id)
        except SQLAlchemyError:
            raise HTTPException(503, 'Contract repository unavailable.') from None

    return router
