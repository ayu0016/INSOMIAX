from __future__ import annotations

from fastapi import APIRouter, Depends

from ..security import require_local_workflow_user
from .models import CandidateProfile, ProfilePreviewResponse
from .service import preview_profile

router = APIRouter(prefix="/api/v1/profiles", tags=["Profile Builder"])


@router.post("/preview", response_model=ProfilePreviewResponse, summary="Validate and preview a session-only candidate profile")
def profile_preview(profile: CandidateProfile, _user: dict = Depends(require_local_workflow_user)) -> ProfilePreviewResponse:
    return preview_profile(profile)
