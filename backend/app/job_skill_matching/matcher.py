from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path

from ..config import PROJECT_ROOT
from ..errors import RadixError
from ..profile_builder.models import CandidateProfile, ProfileSkill
from .models import CandidateEvidence, MatchFinding, SkillMatchRequest, SkillMatchResponse, SkillMappings

DEFAULT_MAPPING_FILE = Path(__file__).with_name("approved_mappings.json")


def normalize_exact_skill(value: str) -> str:
    """Normalize Unicode, case and whitespace only; preserve punctuation and meaning."""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def load_mappings(path: str | None = None) -> SkillMappings:
    source = Path(path) if path else DEFAULT_MAPPING_FILE
    if not source.is_absolute():
        source = PROJECT_ROOT / source
    try:
        mappings = SkillMappings.model_validate(json.loads(source.read_text(encoding="utf-8")))
        claimed: dict[tuple[str, str], str] = {}
        for mapping in mappings.mappings:
            canonical = normalize_exact_skill(mapping.canonical_skill)
            if not canonical:
                raise ValueError
            terms = [mapping.canonical_skill, *mapping.aliases]
            for term in terms:
                normalized = normalize_exact_skill(term)
                if not normalized:
                    raise ValueError
                key = (mapping.category_code, normalized)
                previous = claimed.get(key)
                if previous is not None and previous != canonical:
                    raise ValueError
                claimed[key] = canonical
        return mappings
    except (OSError, ValueError, TypeError):
        raise RadixError(500, "INVALID_MATCH_MAPPING", "The configured skill mapping file is missing or invalid.") from None


def _mapped_key(skill_name: str, category: str, mappings: SkillMappings) -> tuple[str, bool]:
    direct = normalize_exact_skill(skill_name)
    for mapping in mappings.mappings:
        if mapping.category_code != category:
            continue
        canonical = normalize_exact_skill(mapping.canonical_skill)
        if direct == canonical or any(direct == normalize_exact_skill(alias) for alias in mapping.aliases):
            return canonical, direct != canonical
    return direct, False


def _term_in_text(skill_name: str, text: str) -> bool:
    # Literal, case-insensitive phrase mention. Punctuation is preserved to avoid C/C++-style conflation.
    escaped = re.escape(" ".join(skill_name.strip().split())).replace(r"\ ", r"\s+")
    pattern = re.compile(r"(?<![\w+#.])" + escaped + r"(?![\w+#.])", re.I)
    return pattern.search(text) is not None


def _candidate_evidence(skill: ProfileSkill) -> CandidateEvidence:
    return CandidateEvidence(skill_name=skill.skill_name, category_code=skill.category_code, source=skill.source, evidence=skill.evidence or skill.skill_name, source_section=skill.source_section, evidence_kind=skill.evidence_kind, confidence=skill.confidence, proficiency_level=skill.proficiency_level, proficiency_status=skill.proficiency_status)


def _collect_evidence(skill_name: str, category_code: str, profile: CandidateProfile) -> list[CandidateEvidence]:
    found: dict[tuple[str, str, str], CandidateEvidence] = {}
    for skill in profile.skills:
        if _term_in_text(skill_name, skill.skill_name):
            item = _candidate_evidence(skill)
            if skill.category_code != category_code:
                item.review_note = "category_mismatch"
            found[(item.skill_name, item.source, item.evidence)] = item
    for section, source_name in ((profile.work_experience, "work_experience"), (profile.internships, "internship"), (profile.projects, "project")):
        for entry in section:
            if _term_in_text(skill_name, entry.text):
                item = CandidateEvidence(skill_name=skill_name, category_code=category_code, source=source_name, evidence=entry.evidence or entry.text, source_section=entry.source_section or source_name, evidence_kind="inferred", proficiency_level=None, proficiency_status="not_assessed")
                found[(item.skill_name, item.source, item.evidence)] = item
    return list(found.values())


def _finding(job_skill, profile: CandidateProfile, mappings: SkillMappings) -> MatchFinding:
    candidates = _collect_evidence(job_skill.skill_name, job_skill.category_code, profile)
    mapped_job, job_used_alias = _mapped_key(job_skill.skill_name, job_skill.category_code, mappings)
    alias_candidates: list[CandidateEvidence] = []
    if not candidates:
        for skill in profile.skills:
            mapped_candidate, candidate_used_alias = _mapped_key(skill.skill_name, skill.category_code, mappings)
            if skill.category_code == job_skill.category_code and mapped_candidate == mapped_job and (job_used_alias or candidate_used_alias):
                alias_candidates.append(_candidate_evidence(skill))
        candidates = alias_candidates

    if job_skill.confidence != "high":
        classification = "needs_review"
        explanation = "The job skill extraction has uncertain confidence. Review the source excerpt before relying on this comparison."
    elif candidates:
        conflicts = [item for item in candidates if item.review_note == "category_mismatch"]
        valid_candidates = [item for item in candidates if item.review_note != "category_mismatch"]
        if valid_candidates and any(item.evidence_kind == "inferred" for item in valid_candidates):
            candidates = valid_candidates
            classification = "partially_matched"
            explanation = "The skill term appears in work, internship, or project evidence, or is marked inferred. Review the excerpt; a mention does not verify proficiency."
        elif valid_candidates and alias_candidates:
            candidates = valid_candidates
            classification = "matched"
            explanation = "The terms resolve through an explicitly configured category-scoped mapping. Review the evidence; a mapping does not verify proficiency."
        elif valid_candidates:
            candidates = valid_candidates
            classification = "matched"
            explanation = "An exact normalized skill-name match is documented in the profile. This does not verify proficiency or qualification."
        else:
            candidates = conflicts
            classification = "needs_review"
            explanation = "The exact skill name is present, but its profile category conflicts with the job requirement; review the source classification."
    elif job_skill.category_code == "OTHER" or job_skill.confidence != "high" or any(skill.category_code == job_skill.category_code for skill in profile.skills):
        related_category = [skill for skill in profile.skills if skill.category_code == job_skill.category_code]
        if related_category and job_skill.category_code != "OTHER" and job_skill.confidence == "high":
            candidates = [_candidate_evidence(skill) for skill in related_category]
            classification = "needs_review"
            explanation = "The candidate has different skills in the same broad category, but no approved mapping connects them to this requirement. Review rather than assuming equivalence."
        else:
            classification = "needs_review"
            explanation = "The job skill is outside the configured benchmark categories or has uncertain extraction confidence; no unsupported equivalence was assumed."
    else:
        classification = "missing"
        explanation = "No exact skill-name match or explicitly configured mapping was found in profile skills, work, internships, or projects."
    return MatchFinding(job_skill=job_skill.skill_name, category_code=job_skill.category_code, requirement_type=job_skill.requirement_type, classification=classification, explanation=explanation, job_evidence=job_skill.evidence, candidate_evidence=candidates)


def match_skills(request: SkillMatchRequest, mappings_path: str | None = None) -> SkillMatchResponse:
    mappings = load_mappings(mappings_path or os.getenv("RADIX_MATCH_SKILL_MAPPINGS_PATH"))
    findings = [_finding(skill, request.candidate_profile, mappings) for skill in request.job_description.skills]
    return SkillMatchResponse(job_title=request.job_description.job_title, job_source_file=request.job_description.source_file, candidate_name=request.candidate_profile.name.value if request.candidate_profile.name else None, candidate_source_file=request.candidate_profile.source_file, matched=[item for item in findings if item.classification == "matched"], partially_matched=[item for item in findings if item.classification == "partially_matched"], missing=[item for item in findings if item.classification == "missing"], needs_review=[item for item in findings if item.classification == "needs_review"])
