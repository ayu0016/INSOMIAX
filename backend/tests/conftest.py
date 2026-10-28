from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.repository import get_repository
from app.security import require_supabase_user


@pytest.fixture
def client():
    app.dependency_overrides[require_supabase_user] = lambda: {"id": "test-user"}
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


