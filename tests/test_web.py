"""Offline route checks: no startup, personal source files, or provider calls."""
from types import SimpleNamespace
from threading import Lock

import pytest
from fastapi.testclient import TestClient
from backend import web
from backend.web_limits import RequestQuota


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(web, "PUBLIC_ORIGIN", "")
    web.app.state.chat_enabled = True
    web.app.state.generation_lock = Lock()
    web.app.state.quota = RequestQuota(2, 3)
    web.app.state.originals = {"cv.pdf": SimpleNamespace(original=b"%PDF-test", media_type="application/pdf")}

    class Assistant:
        def ask(self, question):
            return SimpleNamespace(answer="Supported answer", status="answered", sources=[])

    web.app.state.assistant = Assistant()
    # Without a context manager, TestClient does not run the real lifespan.
    test_client = TestClient(web.app, base_url="http://localhost")
    yield test_client
    test_client.close()


def test_health_never_needs_generation(client):
    web.app.state.assistant = None
    assert client.get("/health").json() == {"status": "ok"}


def test_validation_origin_and_quota(client):
    assert client.post("/api/chat", json={"question": " "}).status_code == 422
    assert client.post("/api/chat", json={"question": "x" * 2001}).status_code == 422
    assert client.post("/api/chat", json={"question": "Hi"}, headers={"Origin": "https://other.example"}).status_code == 403
    for _ in range(2):
        assert client.post("/api/chat", json={"question": "Hi"}).status_code == 200
    assert client.post("/api/chat", json={"question": "Hi"}).status_code == 429


def test_kill_switch(client):
    web.app.state.chat_enabled = False
    web.app.state.assistant = None
    assert client.post("/api/chat", json={"question": "Hi"}).status_code == 503


def test_original_allowlist(client):
    response = client.get("/api/sources/cv.pdf")
    assert response.content == b"%PDF-test"
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/api/sources/secret.txt").status_code == 404


def test_busy_lock_does_not_consume_quota(client):
    web.app.state.generation_lock.acquire()
    try:
        assert client.post("/api/chat", json={"question": "Hi"}).status_code == 429
        assert not web.app.state.quota.calls
    finally:
        web.app.state.generation_lock.release()


def test_rolling_limits():
    quota = RequestQuota(1, 2)
    assert quota.allow(0)
    assert not quota.allow(1)
    assert quota.allow(3600)
    assert not quota.allow(7200)
    assert quota.allow(86400)
