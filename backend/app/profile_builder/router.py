from __future__ import annotations

from fastapi import APIRouter, Depends

from ..jd_analytics.router import require_jd_access
from .models import CandidateProfile, ProfilePreviewResponse
from .service import preview_profile

router = APIRouter(prefix="/api/v1/profiles", tags=["Profile Builder"])


@router.post("/preview", response_model=ProfilePreviewResponse, summary="Validate and preview a session-only candidate profile")
def profile_preview(profile: CandidateProfile, _user: dict = Depends(require_jd_access)) -> ProfilePreviewResponse:
    return preview_profile(profile)
