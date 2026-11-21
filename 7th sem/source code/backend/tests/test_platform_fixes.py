"""WebSocket auth without URL tokens, log redaction, error notices, and live LLM health checks."""
import logging
import uuid

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel

import app.agent.llm_loader as llm_loader
import app.agent.nodes.composer as composer
from app.auth.utils import WS_AUTH_SUBPROTOCOL
from app.config import settings
from app.log_redaction import RedactTokensFilter, redact_tokens
from app.main import app
from app.routes.auth import limiter

client = TestClient(app)


@pytest.fixture(autouse=True)
def _no_rate_limit():
    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture
def user():
    username = f"fix_{uuid.uuid4().hex[:8]}"
    client.post("/api/auth/register", json={"username": username, "email": f"{username}@novabyte.io", "password": "Passw0rd!23"})
    token = client.post("/api/auth/login", data={"username": username, "password": "Passw0rd!23"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    session_id = client.get("/api/sessions", headers=headers).json()["sessions"][0]["session_id"]
    profile = {"name": username, "email": f"{username}@novabyte.io", "role": "Backend", "skills": [],
               "programming_languages": ["Python"], "tech_stack": ["FastAPI"], "years_of_experience": 1,
               "current_projects": "", "past_experience": "", "github_username": "", "preferred_tools": [],
               "timezone": "UTC"}
    assert client.put("/api/profile", headers=headers, json=profile).json()["profile_completed"] is True
    return token, headers, session_id


# ------------------------------------------------------------------ 1. tokens out of URLs and logs

def test_chat_websocket_authenticates_via_subprotocol(user):
    token, _, session_id = user
    with client.websocket_connect(f"/api/ws/chat/{session_id}", subprotocols=[WS_AUTH_SUBPROTOCOL, token]) as ws:
        assert ws.accepted_subprotocol == WS_AUTH_SUBPROTOCOL


def test_chat_websocket_refuses_incomplete_profiles():
    username = f"fix_{uuid.uuid4().hex[:8]}"
    client.post("/api/auth/register", json={"username": username, "email": f"{username}@novabyte.io", "password": "Passw0rd!23"})
    token = client.post("/api/auth/login", data={"username": username, "password": "Passw0rd!23"}).json()["access_token"]
    session_id = client.get("/api/sessions", headers={"Authorization": f"Bearer {token}"}).json()["sessions"][0]["session_id"]
    with client.websocket_connect(f"/api/ws/chat/{session_id}", subprotocols=[WS_AUTH_SUBPROTOCOL, token]) as ws:
        assert ws.receive_json()["code"] == "PROFILE_INCOMPLETE"


def test_chat_websocket_rejects_missing_token(user):
    _, _, session_id = user
    with client.websocket_connect(f"/api/ws/chat/{session_id}") as ws:
        assert ws.receive_json() == {"type": "error", "error": "Unauthorized"}


def test_integrations_websocket_authenticates_via_subprotocol(user):
    token, _, _ = user
    with client.websocket_connect("/api/dashboard/ws/integrations", subprotocols=[WS_AUTH_SUBPROTOCOL, token]) as ws:
        assert ws.accepted_subprotocol == WS_AUTH_SUBPROTOCOL


def test_tokens_are_redacted_from_logged_urls():
    assert redact_tokens("/api/ws/chat/s1?token=eyJabc.def.ghi") == "/api/ws/chat/s1?token=<redacted>"
    assert redact_tokens("/x?a=1&access_token=secret&b=2") == "/x?a=1&access_token=<redacted>&b=2"

    record = logging.LogRecord("uvicorn.error", logging.INFO, "", 0, '%s - "WebSocket %s" %s',
                               ("127.0.0.1:1", "/api/ws/chat/s1?token=eyJabc.def", "[accepted]"), None)
    RedactTokensFilter().filter(record)
    assert "eyJabc" not in record.getMessage()
    assert "uvicorn.error" in {n for n in ("uvicorn.error", "uvicorn.access")
                               if any(isinstance(f, RedactTokensFilter) for f in logging.getLogger(n).filters)}


# ------------------------------------------------------------------ 2. failures saved as notices

def test_failed_reply_is_saved_and_returned_as_notice(user, monkeypatch):
    _, headers, session_id = user
    monkeypatch.setattr(composer, "get_llm", lambda *a, **k: _Failing(responses=["unused"]))
    monkeypatch.setattr(settings, "MOCK_LLM_ENABLED", False)

    reply = client.post(f"/api/sessions/{session_id}/chat", headers=headers,
                        json={"content": "What is the PR review policy?"}).json()
    assert reply["role"] == "notice"
    assert composer.is_error_notice_text(reply["content"])

    history = client.get(f"/api/sessions/{session_id}/chat", headers=headers).json()["messages"]
    assert history[-1]["role"] == "notice"
    assert not any(m["role"] == "assistant" and composer.is_error_notice_text(m["content"]) for m in history)


@pytest.mark.parametrize("endpoint", ["chat", "chat/stream"])
def test_blank_chat_message_is_rejected_and_not_saved(user, endpoint):
    _, headers, session_id = user
    before = len(client.get(f"/api/sessions/{session_id}/chat", headers=headers).json()["messages"])

    r = client.post(f"/api/sessions/{session_id}/{endpoint}", headers=headers, json={"content": "   "})
    assert r.status_code == 400

    after = len(client.get(f"/api/sessions/{session_id}/chat", headers=headers).json()["messages"])
    assert after == before


# ------------------------------------------------------------------ 3. live health check

class _Failing(FakeListChatModel):
    def invoke(self, *args, **kwargs):
        raise RuntimeError("Error calling model (RESOURCE_EXHAUSTED): 429 RESOURCE_EXHAUSTED")


@pytest.fixture
def two_providers(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "nvidia")
    monkeypatch.setattr(settings, "LLM_FALLBACK_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "MOCK_LLM_ENABLED", False)
    llm_loader.reset_llm()
    yield monkeypatch
    llm_loader.reset_llm()


def _stub(monkeypatch, models):
    monkeypatch.setattr(llm_loader, "_build_provider",
                        lambda provider, temperature, is_primary: (models.get(provider), f"{provider}-model", None))


def test_health_check_exposes_a_fallback_that_is_out_of_quota(two_providers):
    _stub(two_providers, {"nvidia": FakeListChatModel(responses=["OK"]), "gemini": _Failing(responses=["x"])})
    llm_loader.get_llm()
    info = llm_loader.get_llm_provider_info()
    assert info["fallback"]["status"] == "active"  # configuration alone looks fine...

    health = llm_loader.check_llm_health(force=True)
    assert health["health"] == "ok"
    assert health["fallback"]["health"] == "failing"  # ...but the live check catches it
    assert health["fallback"]["health_error"] == "Quota or rate limit exceeded"


def test_health_check_is_cached(two_providers):
    calls = {"n": 0}

    class Counting(FakeListChatModel):
        def invoke(self, *args, **kwargs):
            calls["n"] += 1
            return super().invoke(*args, **kwargs)

    _stub(two_providers, {"nvidia": Counting(responses=["OK"] * 10)})
    llm_loader.get_llm()
    llm_loader.check_llm_health(force=True)
    llm_loader.check_llm_health()
    assert calls["n"] == 1


def test_llm_status_endpoint_runs_check_only_when_asked(two_providers):
    _stub(two_providers, {"nvidia": FakeListChatModel(responses=["OK"] * 5)})
    llm_loader.get_llm()
    assert "health" not in client.get("/api/system/llm-status").json()
    assert client.get("/api/system/llm-status", params={"check": "true"}).json()["health"] == "ok"
