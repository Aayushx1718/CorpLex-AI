from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from starlette.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from app.config import get_settings
from app.routes import build_router
from app.uploads import UploadLimitMiddleware
from app.analytics import build_analytics_router
from app.ml.routes import build_ml_router
from app.research.routes import build_research_router
from app.finance.routes import build_finance_router
from app.finance.comparison import build_comparison_router
from app.workflows.routes import build_workflow_router
from app.accounts import AccountMiddleware, build_accounts_router, access_state, COOKIE
from fastapi import Request, Response
from app.security import SecurityMiddleware
from app.workbench import build_workbench_router

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args={"connect_timeout": 3})


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    engine.dispose()


app = FastAPI(title="CorpLex AI", version="0.7.0", lifespan=lifespan)
@app.exception_handler(RequestValidationError)
async def safe_validation(request, error):
    if request.url.path.startswith('/api/auth/'):
        return JSONResponse({'detail': 'Use a username of 3–40 letters, numbers, dots, dashes or underscores, and a password of 12–128 characters.'}, status_code=422)
    return await request_validation_exception_handler(request, error)


app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origins,
    allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["*"],
)

app.add_middleware(UploadLimitMiddleware)
app.include_router(build_router(engine))
app.include_router(build_analytics_router(engine))
app.include_router(build_ml_router(settings))
app.include_router(build_research_router(engine, settings))
app.include_router(build_finance_router(engine))
app.include_router(build_comparison_router(engine))
app.include_router(build_workflow_router(engine, settings))
app.include_router(build_workbench_router(engine))
app.include_router(build_accounts_router(engine, settings))
app.add_middleware(AccountMiddleware, engine=engine, settings=settings)
app.add_middleware(SecurityMiddleware, settings=settings)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)


@app.get("/api/access")
def access_status(request: Request, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    try:
        return access_state(engine, settings, request.cookies.get(COOKIE))
    except SQLAlchemyError:
        raise HTTPException(503, 'Workspace authentication storage unavailable. Check migrations.') from None



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
            connection.execute(text("SELECT document_id FROM analytics_latest_documents LIMIT 0"))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database or schema unavailable") from None
    return Health(status="ready")
