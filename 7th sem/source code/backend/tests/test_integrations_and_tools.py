import os
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import httpx

from app.config import settings
from app.integrations.manager import integration_manager
from app.agent.tools.integration_tools import (
    github_create_starter_issue,
    github_verify_repo_access,
    email_send_completion_report,
)


@pytest.fixture(autouse=True)
def restore_settings():
    """Fixture to ensure integration configuration is restored after tests."""
    orig_gh_mode = settings.GITHUB_MODE
    orig_gh_token = settings.GITHUB_TOKEN
    orig_email_mode = settings.EMAIL_MODE
    orig_smtp_host = settings.SMTP_HOST
    orig_smtp_user = settings.SMTP_USER
    orig_smtp_pass = settings.SMTP_PASSWORD
    yield
    settings.GITHUB_MODE = orig_gh_mode
    settings.GITHUB_TOKEN = orig_gh_token
    settings.EMAIL_MODE = orig_email_mode
    settings.SMTP_HOST = orig_smtp_host
    settings.SMTP_USER = orig_smtp_user
    settings.SMTP_PASSWORD = orig_smtp_pass


# ============================================================================
# GitHub Tool Tests
# ============================================================================

def test_github_create_starter_issue_mock_mode():
    """GitHub starter issue creation in mock mode returns structured response without credentials."""
    settings.GITHUB_MODE = "mock"
    settings.GITHUB_TOKEN = ""

    result = github_create_starter_issue.invoke({
        "title": "Set up developer environment",
        "description": "Install node and python dependencies",
        "repo_name": "backend-core",
        "org_name": "NovaByte-AI",
    })

    assert isinstance(result, dict)
    assert result["status"] == "success"
    assert result["mode"] == "mock"
    assert result["ticket_id"] == "GH-backend-core-101"
    assert "github.com/NovaByte-AI/backend-core/issues/101" in result["url"]
    assert result.get("error") is None


def test_github_create_starter_issue_real_mode_success_and_failure():
    """GitHub starter issue creation in real mode handles success and API errors explicitly."""
    settings.GITHUB_MODE = "real"
    settings.GITHUB_TOKEN = "ghp_valid_real_token_123"

    # 1. Success case
    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 201
    mock_post_resp.json.return_value = {
        "number": 42,
        "html_url": "https://github.com/NovaByte-AI/backend-core/issues/42",
    }

    mock_get_verify = MagicMock()
    mock_get_verify.status_code = 200

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_get_verify), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_post_resp):
        res = github_create_starter_issue.invoke({
            "title": "Real API Starter Issue",
            "description": "Testing real dispatch",
            "repo_name": "backend-core",
            "org_name": "NovaByte-AI",
        })

        assert res["status"] == "success"
        assert res["mode"] == "real"
        assert res["ticket_id"] == "GH-#42"
        assert res["url"] == "https://github.com/NovaByte-AI/backend-core/issues/42"

    # 2. Failure case (API returns 403 Forbidden)
    mock_fail_resp = MagicMock()
    mock_fail_resp.status_code = 403
    mock_fail_resp.text = "Forbidden: Insufficient repository permissions"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_get_verify), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_fail_resp):
        res_fail = github_create_starter_issue.invoke({
            "title": "Unauthorized Issue",
            "repo_name": "backend-core",
        })

        assert res_fail["status"] == "error"
        assert res_fail["mode"] == "real"
        assert "403" in res_fail["error"] or "Forbidden" in res_fail["error"]


def test_github_verify_repo_access_mock_and_real():
    """GitHub repo access verification works in mock mode and communicates with API in real mode."""
    # Mock mode
    settings.GITHUB_MODE = "mock"
    res_mock = github_verify_repo_access.invoke({
        "repo_name": "infra-repo",
        "github_handle": "dev-user",
    })
    assert res_mock["status"] == "success"
    assert res_mock["accessible"] is True
    assert res_mock["mode"] == "mock"

    # Real mode - Accessible
    settings.GITHUB_MODE = "real"
    settings.GITHUB_TOKEN = "ghp_valid_token"

    mock_ok = MagicMock()
    mock_ok.status_code = 204
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_ok):
        res_real = github_verify_repo_access.invoke({
            "repo_name": "infra-repo",
            "github_handle": "dev-user",
        })
        assert res_real["status"] == "success"
        assert res_real["accessible"] is True
        assert res_real["mode"] == "real"

    # Real mode - Not accessible (404)
    mock_404 = MagicMock()
    mock_404.status_code = 404
    mock_verify = MagicMock()
    mock_verify.status_code = 200

    async def side_effect_get(url, **kwargs):
        if url.endswith("/user"):
            return mock_verify
        return mock_404


    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=side_effect_get):
        res_not_found = github_verify_repo_access.invoke({
            "repo_name": "secret-repo",
            "github_handle": "dev-user",
        })
        assert res_not_found["status"] == "error"
        assert res_not_found["accessible"] is False
        assert "404" in str(res_not_found.get("error"))


# ============================================================================
# Email Tool Tests
# ============================================================================

def test_email_send_completion_report_mock_and_real():
    """Email completion report tool provides preview file in mock and calls SMTP in real mode."""
    # Mock mode
    settings.EMAIL_MODE = "mock"
    res_mock = email_send_completion_report.invoke({
        "session_id": "test_session_889",
        "recipient": "hr-onboarding@novabyte.io",
        "name": "David Kim",
        "role": "Fullstack Developer",
        "team": "Product",
        "experience_level": "Senior",
        "tech_stack": ["React", "FastAPI", "PostgreSQL"],
        "completed_items": [{"task": "Environment setup"}, {"task": "First PR merged"}],
        "pending_items": [],
        "ticket": "PROD-101",
        "confidence_score": 100.0,
    })

    assert res_mock["status"] == "success"
    assert res_mock["mode"] == "mock"
    assert "file" in res_mock
    assert os.path.exists(res_mock["file"])

    # Real mode - With mocked SMTP
    settings.EMAIL_MODE = "real"
    settings.SMTP_HOST = "smtp.novabyte.io"
    settings.SMTP_PORT = 587
    settings.SMTP_USER = "bot@novabyte.io"
    settings.SMTP_PASSWORD = "production-password"

    mock_smtp_inst = MagicMock()
    with patch("smtplib.SMTP", return_value=mock_smtp_inst):
        res_real = email_send_completion_report.invoke({
            "session_id": "test_session_889",
            "recipient": "hr-onboarding@novabyte.io",
            "name": "David Kim",
            "role": "Fullstack Developer",
        })

        assert res_real["status"] == "success"
        assert res_real["mode"] == "real"
        mock_smtp_inst.send_message.assert_called_once()

    # Real mode - Missing credentials failure
    settings.SMTP_HOST = ""
    res_err = email_send_completion_report.invoke({
        "session_id": "test_session_889",
        "name": "David Kim",
    })
    assert res_err["status"] == "error"
    assert "missing" in res_err["error"].lower()


# ============================================================================
# Independent Configuration & Abstraction Tests
# ============================================================================

def test_independent_integration_modes():
    """Each integration operates in its own mode, and retired integrations are rejected."""
    settings.GITHUB_MODE = "mock"
    settings.EMAIL_MODE = "mock"

    import asyncio

    gh_res = asyncio.run(integration_manager.execute_action("github", "create_issue", {"title": "Task A"}))
    assert gh_res["mode"] == "mock"

    assert set(integration_manager.integrations) == {"email", "github"}
    for retired in ("slack", "jira"):
        with pytest.raises(ValueError, match="Unknown integration"):
            asyncio.run(integration_manager.execute_action(retired, "anything", {}))


def test_retired_integrations_are_gone_from_api_and_database():
    """Slack and Jira are not listed, cannot be connected, and old rows are removed at startup."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db.database import SessionLocal
    from app.db.init_db import init_db
    from app.db.models import UserDB, UserIntegrationDB
    from app.db.demo_seed import seed_demo_dashboard_data

    seed_db = SessionLocal()
    try:
        seed_demo_dashboard_data(seed_db)
    finally:
        seed_db.close()

    client = TestClient(app)
    token = client.post("/api/auth/login", data={"username": "demo_user", "password": "DemoPass123!"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    listed = client.get("/api/dashboard/integrations", headers=headers).json()["integrations"]
    assert {i["id"] for i in listed} == {"github", "email"}
    for retired in ("slack", "jira"):
        assert client.post(f"/api/dashboard/integrations/{retired}/connect", headers=headers).status_code == 404

    db = SessionLocal()
    try:
        user = db.query(UserDB).filter(UserDB.username == "demo_user").one()
        db.add(UserIntegrationDB(user_id=user.id, integration="slack", status="connected"))
        db.commit()
        init_db()
        db.expire_all()
        assert db.query(UserIntegrationDB).filter(UserIntegrationDB.integration.in_(["slack", "jira"])).count() == 0
    finally:
        db.close()
