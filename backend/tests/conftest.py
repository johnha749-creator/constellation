import json
import os
import tempfile
from pathlib import Path

import pytest

# Point the API's audit log at a throwaway file before app.main is imported, so tests never
# write into the real backend/audit/reviews.jsonl.
os.environ["CONSTELLATION_AUDIT_LOG"] = str(Path(tempfile.mkdtemp()) / "reviews.jsonl")


def demo_account(index: int = 0) -> dict:
    from app.main import USERS_PATH

    return json.loads(USERS_PATH.read_text(encoding="utf-8"))["accounts"][index]


@pytest.fixture
def client():
    """An API client signed in as the first demo clinician."""
    from fastapi.testclient import TestClient

    from app.main import app

    account = demo_account()
    client = TestClient(app)
    response = client.post("/api/login", json={"username": account["username"], "password": account["password"]})
    assert response.status_code == 200, response.text
    return client
