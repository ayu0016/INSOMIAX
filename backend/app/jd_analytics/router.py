from __future__ import annotations

import os

from fastapi import APIRouter, Depends, File, UploadFile

from ..security import bearer, require_supabase_user
from .analyzer import analyze_job_description
from .document_parser import configured_max_upload_bytes, extract_upload
from .models import JDAnalysisRequest, JDAnalysisResult, ExtractedDocument
from fastapi.security import HTTPAuthorizationCredentials

router = APIRouter(prefix="/api/v1/jd-analytics", tags=["JD Analytics"])


def require_jd_access(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    # Anonymous operation is deliberately restricted to explicit local development.
    if os.getenv("RADIX_ENV", "production").casefold() == "development" and os.getenv("RADIX_JD_AUTH_MODE", "supabase").casefold() == "local":
        return {"id": "local-development"}
    return require_supabase_user(credentials)


@router.post("/extract", response_model=ExtractedDocument)
async def extract_document(file: UploadFile = File(...), _user: dict = Depends(require_jd_access)) -> ExtractedDocument:
    return await extract_upload(file, configured_max_upload_bytes())


@router.post("/analyze", response_model=JDAnalysisResult)
def analyze(request: JDAnalysisRequest, _user: dict = Depends(require_jd_access)) -> JDAnalysisResult:
    return analyze_job_description(request.text, source_file=request.source_file)
