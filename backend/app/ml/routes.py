from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.ml.service import ModelUnavailable, classify, model_status


class ClauseRequest(BaseModel):
    text: str = Field(min_length=20, max_length=20000)


def build_ml_router(settings):
    router = APIRouter(prefix='/api/ml', tags=['model evaluation'])

    @router.get('/status')
    def status():
        return model_status(settings.ml_dataset_dir, settings.ml_artifacts_dir)

    @router.post('/classify')
    def classify_clause(body: ClauseRequest):
        if not body.text.strip() or '\x00' in body.text:
            raise HTTPException(422, 'Provide valid clause text.')
        try:
            return classify(settings.ml_artifacts_dir, body.text)
        except (ModelUnavailable, ImportError):
            raise HTTPException(503, 'No reviewed clause-type model is available. Business-risk prediction is not implemented.') from None

    return router
