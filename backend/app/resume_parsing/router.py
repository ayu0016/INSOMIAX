from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from ..jd_analytics.document_parser import configured_max_upload_bytes, extract_upload
from ..jd_analytics.models import ExtractedDocument
from ..jd_analytics.router import require_jd_access
from .models import ResumeExtractionRequest, ResumeParseResult
from .parser import parse_resume

router = APIRouter(prefix="/api/v1/resume-parsing", tags=["Resume Parsing"])


@router.post("/extract", summary="Extract text from a resume PDF or DOCX")
async def extract_resume(file: UploadFile = File(...), _user: dict = Depends(require_jd_access)) -> ExtractedDocument:
    return await extract_upload(file, configured_max_upload_bytes())


@router.post("/parse", response_model=ResumeParseResult, summary="Parse reviewed resume text into editable fields")
def parse_resume_text(request: ResumeExtractionRequest, _user: dict = Depends(require_jd_access)) -> ResumeParseResult:
    return parse_resume(request.text, source_file=request.source_file)
