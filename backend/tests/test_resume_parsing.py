from __future__ import annotations

from io import BytesIO

from docx import Document
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.main import app
from app.resume_parsing.parser import parse_resume


def make_docx(text: str) -> bytes:
    document = Document()
    for line in text.splitlines():
        document.add_paragraph(line)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def make_pdf(text: str) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    for index, line in enumerate(text.splitlines()):
        pdf.drawString(54, 760 - (index * 18), line)
    pdf.save()
    return buffer.getvalue()


def sample_resume() -> str:
    return """Asha Verma
asha.verma@example.test
+1 (415) 555-0134
EDUCATION
Bachelor of Science in Computer Science, 2018 - 2022
EXPERIENCE
Software Engineer | Example Labs | Jan 2023 - Present
Built Python services and SQL reporting pipelines over 2 years.
INTERNSHIPS
Data Intern | Sample Institute | 2022
Used Python to clean research datasets.
PROJECTS
Campus Planner - built a Java application.
SKILLS: Python, SQL, Java
CERTIFICATIONS
AWS Certified Developer, 2024
"""


def test_parse_resume_extracts_contact_sections_skills_evidence_and_dates():
    result = parse_resume(sample_resume(), source_file="sample.docx")
    assert result.candidate_name and result.candidate_name.value == "Asha Verma"
    assert result.email and result.email.value == "asha.verma@example.test"
    assert result.phone and "415" in result.phone.value
    assert any("Bachelor of Science" in item.text for item in result.education)
    assert any("Software Engineer" in item.text and item.dates for item in result.work_experience)
    assert any(item.duration == "2 years" for item in result.work_experience)
    assert any("Data Intern" in item.text for item in result.internships)
    assert any("Campus Planner" in item.text for item in result.projects)
    assert any("AWS Certified" in item.text for item in result.certifications)
    explicit = next(skill for skill in result.skills if skill.skill_name == "Python" and skill.evidence_kind == "explicit")
    inferred = next(skill for skill in result.skills if skill.skill_name == "Python" and skill.evidence_kind == "inferred")
    assert explicit.source_section == "skills"
    assert inferred.source_section == "experience"
    assert "Built Python services" in inferred.evidence
    assert explicit.proficiency_level is None
    assert result.proficiency_assessed is False and result.scores_available is False
    assert result.source_file == "sample.docx"


def test_missing_details_remain_unknown_and_skill_mentions_outside_evidence_sections_are_ignored():
    result = parse_resume("Asha Verma\nPython enthusiast.")
    assert result.candidate_name and result.candidate_name.value == "Asha Verma"
    assert result.email is None and result.phone is None
    assert result.education == result.work_experience == result.projects == []
    assert result.skills == []
    assert "email" in result.missing_or_ambiguous
    assert "work_experience_or_internships" in result.missing_or_ambiguous


def test_conflicting_contact_values_are_left_unknown_and_marked_ambiguous():
    result = parse_resume("Name: Asha Verma\nEmail: asha@example.test\nEmail: other@example.test\nPhone: 415-555-0134\nPhone: 212-555-0140")
    assert result.candidate_name is not None
    assert result.email is None and result.phone is None
    assert "email (multiple matches)" in result.missing_or_ambiguous
    assert "phone (multiple matches)" in result.missing_or_ambiguous


def test_role_shaped_first_line_is_not_misreported_as_candidate_name():
    result = parse_resume("Senior Software Engineer\nPython developer.")
    assert result.candidate_name is None


def test_resume_skill_aliases_only_apply_when_explicitly_configured(tmp_path):
    vocab = tmp_path / "vocabulary.json"
    vocab.write_text('{"skills":[{"name":"Rust","category_code":"COD","aliases":["Rust Lang"]}]}', encoding="utf-8")
    text = "SKILLS: Rust Lang"
    result = parse_resume(text, vocabulary_path=str(vocab))
    assert result.skills[0].skill_name == "Rust Lang"
    assert result.skills[0].canonical_skill == "Rust"
    assert result.skills[0].evidence_kind == "explicit"


def test_resume_extract_endpoints_accept_pdf_and_docx_with_authenticated_test_user(client, monkeypatch):
    monkeypatch.setenv("RADIX_ENV", "development")
    monkeypatch.setenv("RADIX_JD_AUTH_MODE", "local")
    docx = make_docx(sample_resume())
    pdf = make_pdf(sample_resume())
    for filename, mime, content in (
        ("resume.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", docx),
        ("resume.pdf", "application/pdf", pdf),
    ):
        extracted = client.post("/api/v1/resume-parsing/extract", files={"file": (filename, content, mime)})
        assert extracted.status_code == 200
        parsed = client.post("/api/v1/resume-parsing/parse", json={"text": extracted.json()["text"], "source_file": filename})
        assert parsed.status_code == 200
        assert parsed.json()["source_type"] == "resume"
        assert parsed.json()["candidate_name"]["value"] == "Asha Verma"
        assert parsed.json()["scores_available"] is False


def test_resume_endpoint_reports_unsupported_malformed_oversized_and_invalid_text(client, monkeypatch):
    monkeypatch.setenv("RADIX_ENV", "development")
    monkeypatch.setenv("RADIX_JD_AUTH_MODE", "local")
    unsupported = client.post("/api/v1/resume-parsing/extract", files={"file": ("cv.txt", b"no", "text/plain")})
    malformed = client.post("/api/v1/resume-parsing/extract", files={"file": ("cv.pdf", b"not pdf", "application/pdf")})
    empty_file = client.post("/api/v1/resume-parsing/extract", files={"file": ("cv.pdf", b"", "application/pdf")})
    assert unsupported.status_code == 415 and unsupported.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"
    assert malformed.status_code == 422 and malformed.json()["error"]["code"] == "UNREADABLE_DOCUMENT"
    assert sample_resume() not in malformed.text
    assert empty_file.status_code == 422 and empty_file.json()["error"]["code"] == "EMPTY_DOCUMENT"
    empty = client.post("/api/v1/resume-parsing/parse", json={"text": "  "})
    assert empty.status_code == 422 and empty.json()["error"]["code"] == "VALIDATION_ERROR"

    monkeypatch.setenv("RADIX_JD_MAX_UPLOAD_BYTES", "20")
    too_large = client.post("/api/v1/resume-parsing/extract", files={"file": ("cv.docx", make_docx(sample_resume()), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert too_large.status_code == 413
    assert too_large.json()["error"]["code"] == "UPLOAD_TOO_LARGE"


def test_resume_parse_preserves_protected_auth_default(monkeypatch):
    configurations = ((None, None), ("development", None), (None, "local"), ("production", "local"))
    for environment, auth_mode in configurations:
        if environment is None:
            monkeypatch.delenv("RADIX_ENV", raising=False)
        else:
            monkeypatch.setenv("RADIX_ENV", environment)
        if auth_mode is None:
            monkeypatch.delenv("RADIX_JD_AUTH_MODE", raising=False)
        else:
            monkeypatch.setenv("RADIX_JD_AUTH_MODE", auth_mode)
        with TestClient(app) as client:
            extracted = client.post("/api/v1/resume-parsing/extract", files={"file": ("resume.docx", make_docx(sample_resume()), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
            parsed = client.post("/api/v1/resume-parsing/parse", json={"text": sample_resume()})
        assert extracted.status_code == parsed.status_code == 401
        assert extracted.json()["error"]["code"] == parsed.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_resume_routes_allow_anonymous_access_in_explicit_local_mode(monkeypatch):
    monkeypatch.setenv("RADIX_ENV", "development")
    monkeypatch.setenv("RADIX_JD_AUTH_MODE", "local")
    with TestClient(app) as client:
        extracted = client.post("/api/v1/resume-parsing/extract", files={"file": ("resume.docx", make_docx(sample_resume()), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
        parsed = client.post("/api/v1/resume-parsing/parse", json={"text": sample_resume()})
    assert extracted.status_code == parsed.status_code == 200
    assert parsed.json()["source_type"] == "resume"
