import os
import re
import pytest
import smtplib
from unittest.mock import MagicMock, patch

from app.config import settings
from app.services.email_generator import (
    generate_email,
    generate_html_email,
    send_email,
    compute_confidence_score,
)
from app.integrations.email import EmailIntegration
from app.integrations.manager import integration_manager


@pytest.fixture(autouse=True)
def restore_settings():
    """Fixture to ensure settings changes during tests are restored."""
    original_mode = settings.EMAIL_MODE
    original_host = settings.SMTP_HOST
    original_port = settings.SMTP_PORT
    original_user = settings.SMTP_USER
    original_pass = settings.SMTP_PASSWORD
    original_from = settings.SMTP_FROM_EMAIL
    original_tls = settings.SMTP_USE_TLS
    original_ssl = settings.SMTP_USE_SSL
    yield
    settings.EMAIL_MODE = original_mode
    settings.SMTP_HOST = original_host
    settings.SMTP_PORT = original_port
    settings.SMTP_USER = original_user
    settings.SMTP_PASSWORD = original_pass
    settings.SMTP_FROM_EMAIL = original_from
    settings.SMTP_USE_TLS = original_tls
    settings.SMTP_USE_SSL = original_ssl


def test_generated_email_contains_required_fields():
    """Preserves backward-compatible plain text structure."""
    payload = {
        "name": "Vanshika Wadhwani",
        "role": "Backend Intern",
        "email": "vanshika@email.com",
        "total": 30,
        "completed": 29,
        "pending": 1,
        "completed_items": ["Set up local env", "Open first PR"],
        "ticket": "FLOW-INTERN-001",
        "confidence_score": 96.7,
    }

    email_text = generate_email(payload)

    assert "Name: Vanshika Wadhwani" in email_text
    assert "Role: Backend Intern" in email_text
    assert "Email: vanshika@email.com" in email_text
    assert "Ticket ID: FLOW-INTERN-001" in email_text
    assert "Confidence Score: 96.7%" in email_text
    assert "Completed: 29" in email_text
    assert "Completed Items: Set up local env, Open first PR" in email_text

    timestamp_match = re.search(r"Generated At: \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", email_text)
    assert timestamp_match is not None


def test_generated_html_email_contains_all_required_metadata():
    """Validates that professional HTML email includes all 13 required fields."""
    payload = {
        "name": "Alex Mercer",
        "email": "alex.mercer@novabyte.io",
        "role": "Senior Cloud Architect",
        "team": "Infrastructure & Platform",
        "experience_level": "Senior",
        "tech_stack": ["Terraform", "Kubernetes", "AWS", "Go"],
        "start_time": "2026-10-01 09:00:00 UTC",
        "completion_time": "2026-10-06 17:00:00 UTC",
        "total": 8,
        "completed": 8,
        "pending": 0,
        "progress": 100,
        "completed_items": [
            {"task": "Set up AWS SSO access", "completion_evidence": "IAM role active"},
            {"task": "Run Terraform plan in staging", "completion_evidence": "Exit code 0"},
        ],
        "pending_items": [],
        "ticket": "INFRA-ONB-902",
        "confidence_score": 100.0,
        "verification_info": "Verified via CLI tool and automated pipeline",
    }

    html_email = generate_html_email(payload)

    # 1. Employee name
    assert "Alex Mercer" in html_email
    # 2. Employee email
    assert "alex.mercer@novabyte.io" in html_email
    # 3. Role
    assert "Senior Cloud Architect" in html_email
    # 4. Team
    assert "Infrastructure &amp; Platform" in html_email or "Infrastructure & Platform" in html_email
    # 5. Experience level
    assert "Senior" in html_email
    # 6. Technology stack
    assert "Terraform, Kubernetes, AWS, Go" in html_email
    # 7. Onboarding start time
    assert "2026-10-01 09:00:00 UTC" in html_email
    # 8. Completion time
    assert "2026-10-06 17:00:00 UTC" in html_email
    # 9. Completed tasks & evidence
    assert "Set up AWS SSO access" in html_email
    assert "IAM role active" in html_email
    # 10. Pending tasks
    assert "All required tasks completed" in html_email
    # 11. Overall progress
    assert "100%" in html_email
    # 12. Starter ticket
    assert "INFRA-ONB-902" in html_email
    # 13. Confidence / verification information
    assert "100.0%" in html_email
    assert "Verified via CLI tool and automated pipeline" in html_email


def test_mock_email_mode_saves_file_without_credentials(tmp_path):
    """Mock mode continues generating/storing email preview without SMTP credentials."""
    settings.EMAIL_MODE = "mock"
    settings.SMTP_HOST = ""
    settings.SMTP_USER = ""
    settings.SMTP_PASSWORD = ""

    integration = EmailIntegration()
    assert integration.mode == "mock"

    params = {
        "name": "Jordan Lee",
        "email": "jordan@novabyte.io",
        "role": "Frontend Engineer",
        "team": "Product UI",
        "experience_level": "Mid-Level",
        "tech_stack": ["React", "TypeScript", "Vite"],
        "start_time": "2026-10-06 10:00:00 UTC",
        "completion_time": "2026-10-06 15:00:00 UTC",
        "total": 5,
        "completed": 5,
        "pending": 0,
        "ticket": "FE-START-101",
    }

    import asyncio
    result = asyncio.run(integration.send_completion_email(params))

    assert result["status"] == "success"
    assert result["mode"] == "mock"
    assert "file" in result
    assert os.path.exists(result["file"])

    with open(result["file"], "r", encoding="utf-8") as f:
        content = f.read()
        assert "Jordan Lee" in content
        assert "Frontend Engineer" in content


def test_real_email_mode_smtp_success_with_mocked_smtp(monkeypatch):
    """Real mode delivers via SMTP using environment variables and mocked smtplib."""
    for key, value in {"EMAIL_MODE": "real", "SMTP_HOST": "smtp.mailprovider.com", "SMTP_PORT": 587,
                       "SMTP_USER": "onboarding-bot@novabyte.io", "SMTP_PASSWORD": "safe-production-password",
                       "SMTP_USE_TLS": True, "SMTP_USE_SSL": False}.items():
        monkeypatch.setattr(settings, key, value)
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "onboarding-bot@novabyte.io")
    monkeypatch.setattr(settings, "SMTP_FROM_NAME", "NovaByte Onboarding")

    integration = EmailIntegration()
    import asyncio

    mock_smtp_instance = MagicMock()
    with patch("smtplib.SMTP", return_value=mock_smtp_instance) as mock_smtp_cls:
        # verify() now performs a real login, so it is checked against the mocked server.
        assert asyncio.run(integration.verify()) is True
        mock_smtp_cls.reset_mock()
        mock_smtp_instance.reset_mock()
        params = {
            "name": "Sarah Connor",
            "email": "sarah@novabyte.io",
            "role": "Security Engineer",
            "recipient": "hr@novabyte.io",
            "total": 10,
            "completed": 10,
            "pending": 0,
            "ticket": "SEC-001",
        }

        result = asyncio.run(integration.send_completion_email(params))

        # Check SMTP interactions
        mock_smtp_cls.assert_called_once_with("smtp.mailprovider.com", 587, timeout=15)
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with("onboarding-bot@novabyte.io", "safe-production-password")
        mock_smtp_instance.send_message.assert_called_once()
        mock_smtp_instance.quit.assert_called_once()

        # Check sent message MIME parts
        sent_msg = mock_smtp_instance.send_message.call_args[0][0]
        assert sent_msg["To"] == "hr@novabyte.io"
        assert sent_msg["From"] == "NovaByte Onboarding <onboarding-bot@novabyte.io>"
        assert "Sarah Connor" in sent_msg["Subject"]
        assert sent_msg.is_multipart()

        assert result["status"] == "success"
        assert result["mode"] == "real"


def test_real_email_mode_fails_when_credentials_missing(monkeypatch):
    """Real mode fails clearly when required SMTP credentials are missing."""
    for key, value in {"EMAIL_MODE": "real", "SMTP_HOST": "", "SMTP_USER": "", "SMTP_PASSWORD": ""}.items():
        monkeypatch.setattr(settings, key, value)

    integration = EmailIntegration()
    import asyncio
    assert asyncio.run(integration.verify()) is False

    with pytest.raises(ValueError, match="SMTP configuration missing"):
        asyncio.run(integration.send_completion_email({"name": "Test User"}))


def test_real_email_mode_fails_and_does_not_report_success_on_smtp_error(monkeypatch):
    """Real mode NEVER reports success when SMTP delivery throws an error."""
    for key, value in {"EMAIL_MODE": "real", "SMTP_HOST": "smtp.mailprovider.com", "SMTP_PORT": 587,
                       "SMTP_USER": "onboarding-bot@novabyte.io", "SMTP_PASSWORD": "safe-production-password",
                       "SMTP_USE_TLS": True, "SMTP_USE_SSL": False}.items():
        monkeypatch.setattr(settings, key, value)

    integration = EmailIntegration()

    mock_smtp_instance = MagicMock()
    mock_smtp_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Authentication failed")

    with patch("smtplib.SMTP", return_value=mock_smtp_instance):
        with pytest.raises(RuntimeError, match="SMTP delivery failed"):
            import asyncio
            asyncio.run(integration.send_completion_email({"name": "Test User"}))


def test_welcome_email_mock_and_real_delivery(monkeypatch):
    """Tests welcome email sending in both mock and real modes."""
    # 1. Mock mode
    monkeypatch.setattr(settings, "EMAIL_MODE", "mock")
    integration = EmailIntegration()

    import asyncio
    mock_res = asyncio.run(integration.send_welcome_email({
        "recipient": "newbie@novabyte.io",
        "name": "Newbie Dev",
        "role": "Frontend Developer",
    }))
    assert mock_res["status"] == "success"
    assert mock_res["mode"] == "mock"
    assert os.path.exists(mock_res["file"])

    # 2. Real mode with mocked SMTP
    for key, value in {"EMAIL_MODE": "real", "SMTP_HOST": "smtp.mailprovider.com", "SMTP_PORT": 587,
                       "SMTP_USER": "onboarding-bot@novabyte.io", "SMTP_PASSWORD": "safe-production-password",
                       "SMTP_USE_TLS": True, "SMTP_USE_SSL": False}.items():
        monkeypatch.setattr(settings, key, value)

    mock_smtp_instance = MagicMock()
    with patch("smtplib.SMTP", return_value=mock_smtp_instance):
        real_res = asyncio.run(integration.send_welcome_email({
            "recipient": "newbie@novabyte.io",
            "name": "Newbie Dev",
            "role": "Frontend Developer",
        }))
        assert real_res["status"] == "success"
        assert real_res["mode"] == "real"
        mock_smtp_instance.send_message.assert_called_once()