from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.profile_builder.models import CandidateProfile
from app.profile_builder.service import preview_profile


def example_profile() -> dict:
    return {
        "name": {"value": "Asha Verma", "source": "resume", "edited_by_user": False, "evidence": "Asha Verma"},
        "email": {"value": "asha@example.test", "source": "resume", "edited_by_user": False, "evidence": "asha@example.test"},
        "phone": None,
        "education": [{"text": "BSc Computer Science", "source": "resume", "edited_by_user": False, "evidence": "BSc Computer Science", "source_section": "education", "dates": "2019-2023", "duration": None}],
        "work_experience": [{"text": "Software Engineer at Example Labs", "source": "resume", "edited_by_user": False, "evidence": "Software Engineer at Example Labs", "source_section": "experience", "dates": None, "duration": None}],
        "internships": [],
        "projects": [{"text": "Campus planner project", "source": "manual", "edited_by_user": True, "evidence": None, "source_section": None, "dates": None, "duration": None}],
        "skills": [{"skill_name": "Python", "category_code": "COD", "source": "resume", "edited_by_user": False, "evidence": "Built Python services", "confidence": "high", "canonical_skill": "Python", "evidence_kind": "inferred", "proficiency_level": None, "proficiency_status": "not_assessed"}],
        "certifications": [{"text": "Cloud fundamentals certificate", "source": "manual", "edited_by_user": False, "evidence": None, "source_section": None, "dates": None, "duration": None}],
        "hackathons": [],
        "preferred_roles": [],
        "source_file": "resume.docx",
    }


def test_valid_nested_profile_and_preview_preserve_evidence_provenance_and_unknown_dates():
    profile = CandidateProfile.model_validate(example_profile())
    result = preview_profile(profile)
    assert result.profile.skills[0].source == "resume"
    assert result.profile.skills[0].evidence == "Built Python services"
    assert result.profile.work_experience[0].dates is None
    assert result.persistence_available is False and result.scores_available is False
    assert "Phone number was not provided; it is optional." in result.warnings
    assert any("no identified date" in warning for warning in result.warnings)
    assert any("does not establish proficiency" in warning for warning in result.warnings)
    assert any("proficiency is unknown" in warning for warning in result.warnings)


@pytest.mark.parametrize("change", [
    {"email": {"value": "not-an-email", "source": "manual"}},
    {"education": [{"text": "   "}]},
    {"skills": [{"skill_name": "Python", "category_code": "NOT_A_CATEGORY"}]},
    {"skills": [{"skill_name": "Python", "category_code": "COD", "source": "resume", "proficiency_level": 5}]},
    {"unknown_field": "unexpected"},
])
def test_invalid_nested_profile_payload_is_rejected(change):
    payload = example_profile() | change
    with pytest.raises(ValidationError):
        CandidateProfile.model_validate(payload)


def test_manual_proficiency_must_be_explicitly_user_reported():
    profile = CandidateProfile.model_validate({"skills": [{"skill_name": "Python", "category_code": "COD", "source": "manual", "proficiency_level": 7, "proficiency_status": "user_reported"}]})
    assert profile.skills[0].proficiency_level == 7
    assert profile.skills[0].proficiency_status == "user_reported"


def test_profile_preview_api_returns_validation_error_envelope_for_authenticated_user(client, monkeypatch):
    monkeypatch.setenv("RADIX_ENV", "development")
    monkeypatch.setenv("RADIX_JD_AUTH_MODE", "local")
    valid = client.post("/api/v1/profiles/preview", json=example_profile())
    invalid = client.post("/api/v1/profiles/preview", json=example_profile() | {"extra": True})
    assert valid.status_code == 200
    assert valid.json()["profile"]["name"]["value"] == "Asha Verma"
    assert valid.json()["profile"]["skills"][0]["evidence"] == "Built Python services"
    assert valid.json()["persistence_available"] is False
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "request_id" in invalid.json()["error"]


def test_profile_preview_allows_anonymous_access_in_explicit_local_mode(monkeypatch):
    monkeypatch.setenv("RADIX_ENV", "development")
    monkeypatch.setenv("RADIX_JD_AUTH_MODE", "local")
    with TestClient(app) as client:
        response = client.post("/api/v1/profiles/preview", json=example_profile())
    assert response.status_code == 200
    assert response.json()["profile"]["name"]["value"] == "Asha Verma"
    assert response.json()["persistence_available"] is False


def test_profile_preview_requires_authentication_when_local_mode_is_not_configured(monkeypatch):
    monkeypatch.delenv("RADIX_ENV", raising=False)
    monkeypatch.delenv("RADIX_JD_AUTH_MODE", raising=False)
    with TestClient(app) as client:
        response = client.post("/api/v1/profiles/preview", json=example_profile())
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
