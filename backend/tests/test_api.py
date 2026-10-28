from __future__ import annotations

from unittest.mock import Mock

from app.errors import DatabaseConfigurationRequired
from app.repository import get_repository
from app.security import require_supabase_user


def test_health_reports_configuration_without_exposing_values(client, monkeypatch):
    monkeypatch.setenv("RADIX_SUPABASE_READONLY_DSN", "postgresql://private-password@db")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "private-anon-placeholder")
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["database_configured"] is True
    assert response.json()["auth_configured"] is True
    assert "private-password" not in response.text
    assert "private-anon-placeholder" not in response.text


def test_health_does_not_treat_example_placeholders_as_configured(client, monkeypatch):
    monkeypatch.setenv(
        "RADIX_SUPABASE_READONLY_DSN",
        "postgresql://READ_ONLY_USER:REPLACE_ME@DB_HOST:5432/postgres?sslmode=require",
    )
    monkeypatch.setenv("SUPABASE_URL", "https://PROJECT_REF.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "REPLACE_WITH_SUPABASE_PUBLISHABLE_OR_ANON_KEY")

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["database_configured"] is False
    assert response.json()["auth_configured"] is False


def test_source_endpoint_returns_configuration_required(client):
    repository = Mock()
    repository.inspect_source.side_effect = DatabaseConfigurationRequired()
    from app.main import app
    app.dependency_overrides[get_repository] = lambda: repository

    response = client.get("/api/v1/talent-check/source")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_CONFIGURATION_REQUIRED"
    assert response.json()["error"]["details"]["required_environment_variable"] == "RADIX_SUPABASE_READONLY_DSN"
    repository.inspect_source.assert_called_once()


def test_source_endpoint_reports_unverified_schema_and_never_raw_rows(client):
    repository = Mock()
    repository.inspect_source.return_value.as_dict.return_value = {
        "status": "schema_verification_required",
        "competencies_available": False,
        "readiness_scoring_available": False,
        "reason": "Operator review is needed.",
    }
    from app.main import app
    app.dependency_overrides[get_repository] = lambda: repository

    response = client.get("/api/v1/talent-check/source")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SCHEMA_VERIFICATION_REQUIRED"
    response_text = response.text.lower()
    assert '"columns":' not in response_text
    assert '"row_count":' not in response_text
    assert '"source_schema":' not in response_text
    assert "staging_company_skill_levels" not in response_text


def test_competencies_endpoint_stays_blocked_until_staging_columns_are_verified(client):
    repository = Mock()
    repository.inspect_source.side_effect = DatabaseConfigurationRequired()
    from app.main import app
    app.dependency_overrides[get_repository] = lambda: repository

    response = client.get("/api/v1/talent-check/competencies")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_CONFIGURATION_REQUIRED"
    assert "company" not in response.json()
    repository.inspect_source.assert_called_once()


def test_source_endpoint_sanitizes_database_unavailable_error(client):
    from app.errors import DatabaseUnavailable
    repository = Mock()
    repository.inspect_source.side_effect = DatabaseUnavailable()
    from app.main import app
    app.dependency_overrides[get_repository] = lambda: repository

    response = client.get("/api/v1/talent-check/source")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert "password" not in response.text.lower()
    assert "dsn" not in response.text.lower()


def test_source_endpoint_does_not_expose_ambiguous_schema_names(client):
    from app.errors import SourceSchemaAmbiguous
    repository = Mock()
    repository.inspect_source.side_effect = SourceSchemaAmbiguous(["private_competencies", "legacy_archive"])
    from app.main import app
    app.dependency_overrides[get_repository] = lambda: repository

    response = client.get("/api/v1/talent-check/source")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SOURCE_SCHEMA_AMBIGUOUS"
    assert "private_competencies" not in response.text
    assert "legacy_archive" not in response.text
    assert "RADIX_STAGING_SCHEMA" in response.text


def test_readiness_endpoint_never_calculates_without_approved_policy(client):
    response = client.post(
        "/api/v1/talent-check/readiness",
        json={"company_identifier": "provided-by-user", "candidate_skill_levels": {}},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SCORING_POLICY_UNAPPROVED"


def test_readiness_request_rejects_other_and_invalid_levels(client):
    for payload in (
        {"company_identifier": "company", "candidate_skill_levels": {"OTHER": 5}},
        {"company_identifier": "company", "candidate_skill_levels": {"COD": 0}},
        {"company_identifier": "company", "candidate_skill_levels": {"COD": True}},
    ):
        response = client.post("/api/v1/talent-check/readiness", json=payload)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_company_talent_check_stays_protected_even_in_local_workflow_mode(client, monkeypatch):
    from app.main import app
    monkeypatch.setenv("RADIX_ENV", "development")
    monkeypatch.setenv("RADIX_JD_AUTH_MODE", "local")
    app.dependency_overrides.pop(require_supabase_user, None)
    responses = [
        client.get("/api/v1/talent-check/source"),
        client.get("/api/v1/talent-check/competencies"),
        client.post("/api/v1/talent-check/readiness", json={"company_identifier": "x", "candidate_skill_levels": {}}),
    ]
    assert all(response.status_code == 401 for response in responses)
    assert all(response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED" for response in responses)
