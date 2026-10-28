from __future__ import annotations

from io import BytesIO

import pytest
from docx import Document
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.jd_analytics.analyzer import analyze_job_description, normalize_skill_name
from app.jd_analytics.document_parser import extract_upload
from app.errors import RadixError
from app.main import app
from app.security import require_supabase_user
from starlette.datastructures import Headers, UploadFile


@pytest.fixture(autouse=True)
def local_jd_auth(monkeypatch):
    monkeypatch.setenv("RADIX_ENV", "development")
    monkeypatch.setenv("RADIX_JD_AUTH_MODE", "local")


def make_docx(text: str) -> bytes:
    document = Document()
    for line in text.splitlines():
        document.add_paragraph(line)
    result = BytesIO()
    document.save(result)
    return result.getvalue()


def make_pdf(text: str) -> bytes:
    result = BytesIO()
    pdf = canvas.Canvas(result)
    pdf.drawString(72, 720, text)
    pdf.save()
    return result.getvalue()


def make_blank_pdf() -> bytes:
    result = BytesIO()
    canvas.Canvas(result).save()
    return result.getvalue()


@pytest.mark.parametrize("extension,mime,content", [
    ("pdf", "application/pdf", make_pdf("Job Title: Data Engineer")),
    ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", make_docx("Job Title: Data Engineer")),
], ids=["pdf", "docx"])
@pytest.mark.anyio
async def test_extract_valid_pdf_and_docx(extension, mime, content):
    upload = UploadFile(filename=f"job.{extension}", file=BytesIO(content), headers=Headers({"content-type": mime}))
    result = await extract_upload(upload, 100_000)
    assert result.filename == f"job.{extension}"
    assert "Data Engineer" in result.text


@pytest.mark.anyio
async def test_oversized_upload_rejected():
    upload = UploadFile(filename="jd.docx", file=BytesIO(make_docx("text")), headers=Headers({"content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}))
    with pytest.raises(Exception) as error:
        await extract_upload(upload, 10)
    assert getattr(error.value, "code", None) == "UPLOAD_TOO_LARGE"


@pytest.mark.anyio
async def test_malformed_docx_and_empty_document_rejected():
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    for filename, data, expected in [("bad.docx", b"not a zip", "UNREADABLE_DOCUMENT"), ("empty.docx", b"", "EMPTY_DOCUMENT")]:
        upload = UploadFile(filename=filename, file=BytesIO(data), headers=Headers({"content-type": mime}))
        with pytest.raises(Exception) as error:
            await extract_upload(upload, 1000)
        assert getattr(error.value, "code", None) == expected


@pytest.mark.anyio
async def test_valid_but_textless_pdf_is_reported_as_empty_text():
    upload = UploadFile(filename="scan.pdf", file=BytesIO(make_blank_pdf()), headers=Headers({"content-type": "application/pdf"}))
    with pytest.raises(Exception) as error:
        await extract_upload(upload, 100_000)
    assert getattr(error.value, "code", None) == "EMPTY_DOCUMENT_TEXT"


@pytest.mark.anyio
async def test_unsupported_extension_and_mime_rejected():
    upload = UploadFile(filename="notes.txt", file=BytesIO(b"hello"), headers=Headers({"content-type": "text/plain"}))
    with pytest.raises(Exception) as error:
        await extract_upload(upload, 1000)
    assert getattr(error.value, "status_code", None) == 415


def test_analysis_classifies_required_preferred_and_keeps_sentence_evidence():
    result = analyze_job_description("""Job Title: Platform Engineer
Requirements
Required: Python and SQL experience.
Preferred qualifications
AWS is a plus. Communication is preferred.
Responsibilities
Build reliable services.
""")
    assert result.job_title == "Platform Engineer"
    assert {skill.skill_name for skill in result.required_skills} == {"Python", "SQL"}
    assert {skill.skill_name for skill in result.preferred_skills} == {"AWS", "Communication"}
    assert "Python" in result.required_skills[0].evidence
    assert result.responsibilities[0].text == "Build reliable services."
    assert result.scoring_available is False


def test_missing_title_and_experience_stay_unknown_and_unknown_skill_is_not_normalized():
    result = analyze_job_description("Work with Rust. Strong technical background.")
    assert result.job_title is None
    assert result.experience_requirements == []
    assert result.required_skills == result.preferred_skills == result.unclassified_requirement_skills == []
    assert normalize_skill_name("  Data—Structures / Algorithms ") == "data structures algorithms"


def test_configured_vocabulary_and_invalid_vocabulary(tmp_path):
    vocabulary = tmp_path / "vocabulary.json"
    vocabulary.write_text('{"skills":[{"name":"Rust","category_code":"COD","aliases":["Rust Lang"]}]}', encoding="utf-8")
    matched = analyze_job_description("Required Rust Lang.", str(vocabulary)).required_skills[0]
    assert matched.skill_name == "Rust Lang"
    assert matched.canonical_skill == "Rust"
    vocabulary.write_text('{"skills":[{"name":"Rust","category_code":"COD","aliases":["Rust Lang"]},{"name":"Systems Rust","category_code":"SWE","aliases":[" rust   lang "]}]}', encoding="utf-8")
    with pytest.raises(RadixError) as error:
        analyze_job_description("Required Rust Lang.", str(vocabulary))
    assert error.value.code == "INVALID_SKILL_VOCABULARY"
    vocabulary.write_text('{"skills":[{"name":"Nope","category_code":"FAKE"}]}', encoding="utf-8")
    with pytest.raises(RadixError) as error:
        analyze_job_description("Required Nope.", str(vocabulary))
    assert error.value.code == "INVALID_SKILL_VOCABULARY"


def test_api_extract_and_analyze_flow_and_validation_errors():
    with TestClient(app) as client:
        content = make_docx("Job Title: Analyst\nRequired Python.")
        extracted = client.post("/api/v1/jd-analytics/extract", files={"file": ("jd.docx", content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
        assert extracted.status_code == 200
        analyzed = client.post("/api/v1/jd-analytics/analyze", json={"text": extracted.json()["text"]})
        assert analyzed.status_code == 200
        assert analyzed.json()["job_title"] == "Analyst"
        assert analyzed.json()["required_skills"][0]["skill_name"] == "Python"

        invalid = client.post("/api/v1/jd-analytics/analyze", json={"text": "", "extra": True})
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"
        unsupported = client.post("/api/v1/jd-analytics/extract", files={"file": ("bad.txt", b"hello", "text/plain")})
        assert unsupported.status_code == 415
        assert unsupported.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"
        malformed = client.post("/api/v1/jd-analytics/extract", files={"file": ("bad.pdf", b"not a PDF", "application/pdf")})
        assert malformed.status_code == 422
        assert malformed.json()["error"]["code"] == "UNREADABLE_DOCUMENT"


def test_both_jd_endpoints_allow_anonymous_requests_in_explicit_local_mode(monkeypatch):
    monkeypatch.setenv("RADIX_ENV", "development")
    monkeypatch.setenv("RADIX_JD_AUTH_MODE", "local")
    with TestClient(app) as client:
        extracted = client.post("/api/v1/jd-analytics/extract", files={"file": ("jd.docx", make_docx("Job Title: Analyst\nRequired Python."), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
        analyzed = client.post("/api/v1/jd-analytics/analyze", json={"text": "Job Title: Analyst\nRequired Python."})
    assert extracted.status_code == 200
    assert analyzed.status_code == 200


@pytest.mark.parametrize(("environment", "auth_mode"), [
    (None, None),
    ("development", None),
    (None, "local"),
    ("production", "local"),
])
def test_jd_endpoints_require_supabase_unless_both_local_settings_are_explicit(monkeypatch, environment, auth_mode):
    if environment is None:
        monkeypatch.delenv("RADIX_ENV", raising=False)
    else:
        monkeypatch.setenv("RADIX_ENV", environment)
    if auth_mode is None:
        monkeypatch.delenv("RADIX_JD_AUTH_MODE", raising=False)
    else:
        monkeypatch.setenv("RADIX_JD_AUTH_MODE", auth_mode)

    with TestClient(app) as client:
        extracted = client.post("/api/v1/jd-analytics/extract", files={"file": ("jd.docx", make_docx("Job Title: Analyst"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
        analyzed = client.post("/api/v1/jd-analytics/analyze", json={"text": "Job Title: Analyst"})
    assert extracted.status_code == analyzed.status_code == 401
    assert extracted.json()["error"]["code"] == analyzed.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_api_enforces_configured_upload_limit(monkeypatch):
    monkeypatch.setenv("RADIX_JD_MAX_UPLOAD_BYTES", "10")
    with TestClient(app) as client:
        response = client.post("/api/v1/jd-analytics/extract", files={"file": ("jd.pdf", make_pdf("too large"), "application/pdf")})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "UPLOAD_TOO_LARGE"


def test_supabase_auth_remains_default_outside_explicit_local_mode(monkeypatch):
    monkeypatch.setenv("RADIX_ENV", "production")
    monkeypatch.setenv("RADIX_JD_AUTH_MODE", "local")
    with TestClient(app) as client:
        response = client.post("/api/v1/jd-analytics/analyze", json={"text": "Python"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
