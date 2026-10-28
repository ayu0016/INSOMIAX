from __future__ import annotations

from fastapi import APIRouter, Depends

from ..security import require_supabase_user
from .matcher import match_skills
from .models import SkillMatchRequest, SkillMatchResponse

router = APIRouter(prefix="/api/v1/skill-matches", tags=["Job Skill Matching"])


@router.post("", response_model=SkillMatchResponse, summary="Compare an accepted JD and candidate profile without scoring")
def create_skill_match(request: SkillMatchRequest, _user: dict = Depends(require_supabase_user)) -> SkillMatchResponse:
    return match_skills(request)
