from __future__ import annotations

from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .errors import RadixError, SchemaVerificationRequired, ScoringPolicyUnapproved
from .repository import StagingCompetencyRepository, get_repository
from .schemas import HealthResponse, ReadinessRequest, SourceInspectionResponse
from .security import require_supabase_user
from .jd_analytics.router import router as jd_analytics_router
from .resume_parsing.router import router as resume_parsing_router
from .profile_builder.router import router as profile_builder_router
from .job_skill_matching.router import router as job_skill_matching_router

app = FastAPI(title="RADIX Talent Match API", version="0.1.0")
app.include_router(jd_analytics_router)
app.include_router(resume_parsing_router)
app.include_router(profile_builder_router)
app.include_router(job_skill_matching_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(get_settings().cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID") or str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.exception_handler(RadixError)
async def radix_error_handler(request: Request, exc: RadixError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "request_id": getattr(request.state, "request_id", str(uuid4())),
                "details": exc.details,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    safe_errors = [
        {"loc": [str(item) for item in error.get("loc", ())], "type": error.get("type", "invalid")}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "The request did not match the expected schema.",
                "request_id": getattr(request.state, "request_id", str(uuid4())),
                "details": {"errors": safe_errors},
            }
        },
    )


@app.get("/api/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        database_configured=settings.database_configured,
        auth_configured=settings.auth_configured,
    )


@app.get(
    "/api/v1/talent-check/source",
    response_model=SourceInspectionResponse,
    responses={409: {"description": "Schema review is required"}, 503: {"description": "Source unavailable"}},
)
def inspect_source(
    _user: dict = Depends(require_supabase_user),
    repository: StagingCompetencyRepository = Depends(get_repository),
) -> SourceInspectionResponse:
    inspection = repository.inspect_source().as_dict()
    raise SchemaVerificationRequired(inspection)


@app.get("/api/v1/talent-check/competencies")
def company_competencies(
    _user: dict = Depends(require_supabase_user),
    repository: StagingCompetencyRepository = Depends(get_repository),
) -> None:
    inspection = repository.inspect_source().as_dict()
    raise SchemaVerificationRequired(inspection)


@app.post("/api/v1/talent-check/readiness")
def readiness(
    _request: ReadinessRequest,
    _user: dict = Depends(require_supabase_user),
) -> None:
    raise ScoringPolicyUnapproved()
