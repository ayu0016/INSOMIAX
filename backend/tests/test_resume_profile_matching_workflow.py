from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def profile_prefill_from_resume(resume: dict) -> dict:
    """Build the same typed Profile Builder shape as the frontend prefill adapter."""
    def contact(field):
        return {"value": field["value"], "evidence": field["evidence"], "source": "resume", "edited_by_user": False} if field else None

    def entries(items):
        return [{**item, "source": "resume", "edited_by_user": False} for item in items]

    return {
        "name": contact(resume["candidate_name"]),
        "email": contact(resume["email"]),
        "phone": contact(resume["phone"]),
        "education": entries(resume["education"]),
        "work_experience": entries(resume["work_experience"]),
        "internships": entries(resume["internships"]),
        "projects": entries(resume["projects"]),
        "certifications": entries(resume["certifications"]),
        "skills": [{
            **skill,
            "source": "resume",
            "edited_by_user": False,
            "proficiency_status": "not_assessed",
        } for skill in resume["skills"]],
        "hackathons": [],
        "preferred_roles": [],
        "source_file": resume["source_file"],
    }


def test_resume_artifact_prefills_profile_accepts_then_flows_to_skill_matching(client, monkeypatch):
    monkeypatch.setenv("RADIX_ENV", "development")
    monkeypatch.setenv("RADIX_JD_AUTH_MODE", "local")
    resume_text = """Mira Example
mira@example.test
EDUCATION
Bachelor of Science in Computer Science, 2020 - 2024
EXPERIENCE
Data Analyst | Sample Works | 2024
Built Python analysis scripts.
PROJECTS
Research dashboard built with Python.
SKILLS: Python
"""

    # Resume and profile/matching routes use the authenticated test-user fixture;
    # JD Analytics alone uses the explicitly enabled local anonymous path.
    resume_response = client.post("/api/v1/resume-parsing/parse", json={"text": resume_text, "source_file": "mira-resume.docx"})
    assert resume_response.status_code == 200
    resume_artifact = resume_response.json()
    original_resume_skill = resume_artifact["skills"][0]["skill_name"]

    profile_draft = profile_prefill_from_resume(resume_artifact)
    profile_draft["projects"][0]["text"] += " (reviewed)"
    assert resume_artifact["projects"][0]["text"] != profile_draft["projects"][0]["text"]
    assert resume_artifact["skills"][0]["skill_name"] == original_resume_skill

    preview_response = client.post("/api/v1/profiles/preview", json=profile_draft)
    assert preview_response.status_code == 200
    accepted_profile = preview_response.json()["profile"]
    assert accepted_profile["name"]["value"] == "Mira Example"
    assert accepted_profile["skills"][0]["source"] == "resume"
    assert accepted_profile["skills"][0]["evidence"]
    assert preview_response.json()["persistence_available"] is False

    jd_response = client.post("/api/v1/jd-analytics/analyze", json={"text": "Job Title: Data Analyst\nRequired Python."})
    assert jd_response.status_code == 200
    match_response = client.post("/api/v1/skill-matches", json={
        "job_description": jd_response.json(),
        "candidate_profile": accepted_profile,
    })
    assert match_response.status_code == 200
    findings = match_response.json()
    assert findings["matched"] or findings["partially_matched"]
    assert findings["numerical_score_available"] is False
    assert findings["persisted"] is False


def test_missing_resume_profile_or_jd_inputs_are_rejected(client):
    empty_jd_match = client.post("/api/v1/skill-matches", json={"job_description": {}, "candidate_profile": {}})
    assert empty_jd_match.status_code == 422
    assert empty_jd_match.json()["error"]["code"] == "VALIDATION_ERROR"
