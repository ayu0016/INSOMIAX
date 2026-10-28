from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from ..security import require_local_workflow_user
from .analyzer import analyze_job_description
from .document_parser import configured_max_upload_bytes, extract_upload
from .models import JDAnalysisRequest, JDAnalysisResult, ExtractedDocument

router = APIRouter(prefix="/api/v1/jd-analytics", tags=["JD Analytics"])


@router.post("/extract", response_model=ExtractedDocument)
async def extract_document(file: UploadFile = File(...), _user: dict = Depends(require_local_workflow_user)) -> ExtractedDocument:
    return await extract_upload(file, configured_max_upload_bytes())


@router.post("/analyze", response_model=JDAnalysisResult)
def analyze(request: JDAnalysisRequest, _user: dict = Depends(require_local_workflow_user)) -> JDAnalysisResult:
    return analyze_job_description(request.text, source_file=request.source_file)
