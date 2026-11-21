"""Real (SMTP) email mode, exercised against a fake SMTP server."""
import asyncio
import smtplib

import pytest

import app.services.email_generator as email_generator
from app.config import normalize_smtp_password, settings
from app.integrations.email import EmailIntegration


class FakeSMTP:
    instances = []
    login_error = None

    def __init__(self, host, port, timeout=None):
        self.host, self.port, self.calls, self.sent = host, port, [], []
        FakeSMTP.instances.append(self)

    def ehlo(self):
        self.calls.append("ehlo")

    def starttls(self):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(("login", user, password))
        if FakeSMTP.login_error:
            raise FakeSMTP.login_error

    def send_message(self, msg):
        self.sent.append(msg)

    def close(self):
        self.calls.append("close")

    def quit(self):
        self.calls.append("quit")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.quit()


class FakeSMTPSSL(FakeSMTP):
    pass


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.instances, FakeSMTP.login_error = [], None
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTPSSL)
    for key, value in {
        "EMAIL_MODE": "real", "SMTP_HOST": "smtp.gmail.com", "SMTP_PORT": 587, "SMTP_USE_TLS": True,
        "SMTP_USE_SSL": False, "SMTP_USER": "team@gmail.com", "SMTP_PASSWORD": "abcdefghijklmnop",
        "SMTP_FROM_EMAIL": "team@gmail.com", "SMTP_FROM_NAME": "NovaByte Onboarding",
    }.items():
        monkeypatch.setattr(settings, key, value)
    return monkeypatch


def test_sends_over_starttls_with_standard_headers(smtp):
    result = email_generator.send_email("new.hire@example.com", "Welcome", "Hello", "<p>Hello</p>")

    server = FakeSMTP.instances[-1]
    assert result == {"status": "success", "mode": "real", "recipient": "new.hire@example.com"}
    assert (server.host, server.port) == ("smtp.gmail.com", 587)
    assert "starttls" in server.calls and ("login", "team@gmail.com", "abcdefghijklmnop") in server.calls
    msg = server.sent[0]
    assert msg["From"] == "NovaByte Onboarding <team@gmail.com>"
    assert msg["Date"] and msg["Message-ID"]  # missing either is a common spam signal
    assert "quit" in server.calls


def test_port_465_uses_implicit_ssl(smtp):
    smtp.setattr(settings, "SMTP_PORT", 465)
    email_generator.send_email("a@example.com", "Hi", "Hello")
    server = FakeSMTP.instances[-1]
    assert isinstance(server, FakeSMTPSSL)
    assert "starttls" not in server.calls


def test_rejected_login_explains_gmail_app_passwords(smtp):
    FakeSMTP.login_error = smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")
    with pytest.raises(RuntimeError, match="App Password"):
        email_generator.send_email("a@example.com", "Hi", "Hello")
    assert "close" in FakeSMTP.instances[-1].calls  # connection not leaked


def test_connect_button_verifies_by_logging_in(smtp):
    assert asyncio.run(EmailIntegration().verify()) is True

    FakeSMTP.login_error = smtplib.SMTPAuthenticationError(535, b"bad credentials")
    assert asyncio.run(EmailIntegration().verify()) is False


def test_password_reset_uses_the_shared_sender(smtp):
    from app.routes.auth import _send_password_reset_email

    _send_password_reset_email("user@example.com", "http://localhost:5173/reset-password?token=abc")
    msg = FakeSMTP.instances[-1].sent[0]
    assert msg["To"] == "user@example.com"
    assert msg["From"] == "NovaByte Onboarding <team@gmail.com>"
    assert "reset-password?token=abc" in msg.get_payload()[0].get_payload(decode=True).decode()


def test_gmail_app_password_spaces_are_removed():
    assert normalize_smtp_password(" abcd efgh ijkl mnop ", "smtp.gmail.com") == "abcdefghijklmnop"
    assert normalize_smtp_password("pass with spaces", "smtp.office365.com") == "pass with spaces"
