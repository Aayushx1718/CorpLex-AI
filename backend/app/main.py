from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from app.config import get_settings
from app.routes import build_router
from app.uploads import UploadLimitMiddleware

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args={"connect_timeout": 3})


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    engine.dispose()


app = FastAPI(title="CorpLex AI", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origins,
    allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["*"],
)

app.add_middleware(UploadLimitMiddleware)
app.include_router(build_router(engine))


class Health(BaseModel):
    status: str
    service: str = "corplex-api"


@app.get("/api/health", response_model=Health, tags=["operations"])
def health() -> Health:
    """Liveness: independent of external services."""
    return Health(status="ok")


@app.get("/api/ready", response_model=Health, tags=["operations"])
def ready() -> Health:
    """Readiness: PostgreSQL is reachable and the initial schema is installed."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT document_version_id FROM document_sources LIMIT 0"))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database or schema unavailable") from None
    return Health(status="ready")
