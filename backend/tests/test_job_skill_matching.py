from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.jd_analytics.models import EvidenceText, JDAnalysisResult, SkillEvidence
from app.job_skill_matching.matcher import match_skills, normalize_exact_skill
from app.job_skill_matching.models import SkillMatchRequest
from app.main import app
from app.profile_builder.models import CandidateProfile


def job_skill(name: str, category: str = "COD", requirement: str = "required", evidence: str | None = None, confidence: str = "high") -> SkillEvidence:
    return SkillEvidence(skill_name=name, category_code=category, requirement_type=requirement, evidence=evidence or f"{requirement.title()}: {name}.", confidence=confidence, canonical_skill=None)


def jd(skills: list[SkillEvidence]) -> JDAnalysisResult:
    return JDAnalysisResult(source_file="fictional-role.docx", role="Analyst", job_title="Analyst", job_title_evidence="Job Title: Analyst", skills=skills, required_skills=[s for s in skills if s.requirement_type == "required"], preferred_skills=[s for s in skills if s.requirement_type == "preferred"], unclassified_requirement_skills=[s for s in skills if s.requirement_type == "unspecified"], skills_by_category={}, experience_requirements=[], education_requirements=[], responsibilities=[], key_qualifications=[])


def profile(skills=None, work=None, projects=None) -> CandidateProfile:
    return CandidateProfile.model_validate({
        "name": {"value": "Asha Verma", "source": "manual", "evidence": None},
        "skills": skills or [],
        "work_experience": work or [],
        "projects": projects or [],
        "source_file": "fictional-resume.pdf",
    })


def match(skills, candidate, mappings_path=None):
    return match_skills(SkillMatchRequest(job_description=jd(skills), candidate_profile=candidate), mappings_path)


def test_exact_match_and_requirement_type_are_preserved_with_explanation():
    result = match([job_skill("Python", requirement="required"), job_skill("SQL", "SQL", requirement="preferred")], profile(skills=[
        {"skill_name": "python", "category_code": "COD", "source": "resume", "evidence": "Python", "confidence": "high", "source_section": "skills", "evidence_kind": "explicit"},
        {"skill_name": "SQL", "category_code": "SQL", "source": "manual", "evidence": "Used SQL", "evidence_kind": "manual"},
    ]))
    assert [item.job_skill for item in result.matched] == ["Python", "SQL"]
    assert result.matched[0].requirement_type == "required"
    assert result.matched[1].requirement_type == "preferred"
    assert result.matched[0].candidate_evidence[0].evidence == "Python"
    assert "does not verify proficiency" in result.matched[0].explanation
    assert result.numerical_score_available is False and result.persisted is False


def test_inferred_resume_and_experience_mentions_are_partial_with_excerpt():
    candidate = profile(
        skills=[{"skill_name": "Python", "category_code": "COD", "source": "resume", "evidence": "Created scripts with Python.", "confidence": "high", "source_section": "projects", "evidence_kind": "inferred"}],
        work=[{"text": "Built Python tools.", "source": "resume", "evidence": "Built Python tools.", "source_section": "experience"}],
    )
    result = match([job_skill("Python")], candidate)
    assert len(result.partially_matched) == 1
    assert len(result.partially_matched[0].candidate_evidence) == 2
    assert all(item.evidence_kind == "inferred" for item in result.partially_matched[0].candidate_evidence)
    assert "does not verify proficiency" in result.partially_matched[0].explanation


def test_missing_unknown_terms_and_unapproved_same_category_equivalence_need_review():
    result = match([job_skill("Python", "COD"), job_skill("Go", "COD"), job_skill("Uncatalogued Tool", "OTHER")], profile(skills=[
        {"skill_name": "Rust", "category_code": "COD", "source": "manual", "evidence_kind": "manual"},
        {"skill_name": "Random Tool", "category_code": "OTHER", "source": "manual", "evidence_kind": "manual"},
    ]))
    assert [item.job_skill for item in result.needs_review] == ["Python", "Go", "Uncatalogued Tool"]
    assert all("no approved mapping" in item.explanation or "outside the configured" in item.explanation for item in result.needs_review)
    assert result.missing == []


def test_known_requirement_absent_from_candidate_categories_is_missing():
    result = match([job_skill("Data Structures", "DSA")], profile(skills=[{"skill_name": "Python", "category_code": "COD", "source": "manual", "evidence_kind": "manual"}]))
    assert len(result.missing) == 1
    assert "No exact skill-name match" in result.missing[0].explanation


def test_explicitly_configured_alias_matches_but_unapproved_alias_does_not(tmp_path):
    mapping_file = tmp_path / "mappings.json"
    mapping_file.write_text(json.dumps({"mappings": [{"canonical_skill": "JavaScript", "category_code": "COD", "aliases": ["JS"]}]}), encoding="utf-8")
    requirements = [job_skill("JavaScript", "COD")]
    candidate = profile(skills=[{"skill_name": "JS", "category_code": "COD", "source": "manual", "evidence_kind": "manual"}])
    approved = match(requirements, candidate, str(mapping_file))
    assert len(approved.matched) == 1
    assert "explicitly configured" in approved.matched[0].explanation
    unapproved = match(requirements, candidate)
    assert len(unapproved.needs_review) == 1
    assert not unapproved.matched


def test_duplicate_skills_and_repeated_evidence_are_deduplicated():
    duplicate = {"skill_name": "Python", "category_code": "COD", "source": "resume", "evidence": "Python listed", "source_section": "skills", "evidence_kind": "explicit"}
    result = match([job_skill("Python"), job_skill("Python", evidence="Python is used daily.")], profile(skills=[duplicate, duplicate]))
    assert len(result.matched) == 2  # distinct job evidence is preserved
    assert all(len(item.candidate_evidence) == 1 for item in result.matched)
    assert result.matched[0].job_evidence != result.matched[1].job_evidence


def test_category_conflict_and_uncertain_job_extraction_are_needs_review():
    result = match([job_skill("Python", "COD"), job_skill("Kubernetes", "CLOUD", confidence="low")], profile(skills=[
        {"skill_name": "Python", "category_code": "OTHER", "source": "manual", "evidence_kind": "manual"},
    ]))
    assert result.needs_review[0].job_skill == "Python"
    assert "category conflicts" in result.needs_review[0].explanation
    assert result.needs_review[1].job_skill == "Kubernetes"


def test_invalid_mapping_conflict_fails_clearly_and_normalization_preserves_punctuation(tmp_path):
    mapping_file = tmp_path / "bad.json"
    mapping_file.write_text('{"mappings":[{"canonical_skill":"Python","category_code":"COD","aliases":["Py"]},{"canonical_skill":"PyTorch","category_code":"COD","aliases":["py"]}]}', encoding="utf-8")
    with pytest.raises(Exception) as error:
        match([job_skill("Python")], profile(skills=[{"skill_name": "Python", "category_code": "COD", "source": "manual", "evidence_kind": "manual"}]), str(mapping_file))
    assert getattr(error.value, "code", None) == "INVALID_MATCH_MAPPING"
    assert normalize_exact_skill("  C++  ") == "c++"
    assert normalize_exact_skill(" C ") != normalize_exact_skill("C++")


@pytest.mark.parametrize("payload", [
    {"job_description": {}, "candidate_profile": {}},
    {"job_description": jd([]).model_dump(), "candidate_profile": profile(skills=[{"skill_name": "Python", "category_code": "COD", "source": "manual", "evidence_kind": "manual"}]).model_dump()},
    {"job_description": jd([job_skill("Python")]).model_dump(), "candidate_profile": profile().model_dump()},
])
def test_missing_or_invalid_match_inputs_are_rejected(payload):
    with pytest.raises(ValidationError):
        SkillMatchRequest.model_validate(payload)


def test_matching_endpoint_contract_and_validation_envelope_for_authenticated_user(client, monkeypatch):
    monkeypatch.setenv("RADIX_ENV", "development")
    monkeypatch.setenv("RADIX_JD_AUTH_MODE", "local")
    payload = {"job_description": jd([job_skill("Python")]).model_dump(mode="json"), "candidate_profile": profile(skills=[{"skill_name": "Python", "category_code": "COD", "source": "manual", "evidence_kind": "manual"}]).model_dump(mode="json")}
    valid = client.post("/api/v1/skill-matches", json=payload)
    invalid = client.post("/api/v1/skill-matches", json={"extra": "bad"})
    assert valid.status_code == 200
    assert len(valid.json()["matched"]) == 1
    assert valid.json()["numerical_score_available"] is False
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"


def test_matching_endpoint_keeps_supabase_auth_outside_explicit_local_mode(monkeypatch):
    monkeypatch.setenv("RADIX_ENV", "production")
    monkeypatch.setenv("RADIX_JD_AUTH_MODE", "local")
    with TestClient(app) as client:
        response = client.post("/api/v1/skill-matches", json={})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_matching_endpoint_allows_anonymous_access_in_explicit_local_mode(monkeypatch):
    monkeypatch.setenv("RADIX_ENV", "development")
    monkeypatch.setenv("RADIX_JD_AUTH_MODE", "local")
    payload = {"job_description": jd([job_skill("Python")]).model_dump(mode="json"), "candidate_profile": profile(skills=[{"skill_name": "Python", "category_code": "COD", "source": "manual", "evidence_kind": "manual"}]).model_dump(mode="json")}
    with TestClient(app) as client:
        response = client.post("/api/v1/skill-matches", json=payload)
    assert response.status_code == 200
    assert len(response.json()["matched"]) == 1
    assert response.json()["persisted"] is False


def test_matching_endpoint_requires_authentication_when_local_mode_is_not_configured(monkeypatch):
    monkeypatch.delenv("RADIX_ENV", raising=False)
    monkeypatch.delenv("RADIX_JD_AUTH_MODE", raising=False)
    with TestClient(app) as client:
        response = client.post("/api/v1/skill-matches", json={})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
