from __future__ import annotations

from fastapi import APIRouter, Depends

from ..jd_analytics.router import require_jd_access
from .matcher import match_skills
from .models import SkillMatchRequest, SkillMatchResponse

router = APIRouter(prefix="/api/v1/skill-matches", tags=["Job Skill Matching"])


@router.post("", response_model=SkillMatchResponse, summary="Compare an accepted JD and candidate profile without scoring")
def create_skill_match(request: SkillMatchRequest, _user: dict = Depends(require_jd_access)) -> SkillMatchResponse:
    return match_skills(request)
