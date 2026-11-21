import logging
import os
from pathlib import Path
from typing import Any, Dict
from datetime import datetime

from app.integrations.base import IntegrationBase
from app.config import settings
from app.services.email_generator import generate_email, generate_html_email, send_email

logger = logging.getLogger(__name__)


def _smtp_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)


class EmailIntegration(IntegrationBase):
    """
    Handles sending emails (Welcome, Completion, HR Notification).
    Supports 'mock' mode for local preview without SMTP credentials
    and 'real' mode via standard SMTP delivery using environment variables.
    """

    def __init__(self):
        self.output_dir = settings.BASE_DIR / "sent_emails"
        if getattr(settings, "EMAIL_MODE", "mock").lower() == "mock":
            os.makedirs(self.output_dir, exist_ok=True)

    @property
    def mode(self) -> str:
        return getattr(settings, "EMAIL_MODE", "mock").lower().strip()

    async def verify(self) -> bool:
        """
        Verify Email configuration.
        Returns True in mock mode, or True in real mode if required SMTP credentials exist.
        """
        if self.mode == "mock":
            return True

        # Actually log in, so wrong credentials show as a failed connection instead of "connected".
        import asyncio
        from app.services.email_generator import verify_smtp_connection

        ok, reason = await asyncio.to_thread(verify_smtp_connection)
        if not ok:
            logger.error("SMTP verification failed: %s", reason)
        return ok

    async def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Route to the appropriate action method."""
        if action == "send_completion_email":
            return await self.send_completion_email(params)
        elif action == "send_welcome_email":
            return await self.send_welcome_email(params)
        else:
            raise ValueError(f"Unknown action: {action}")

    async def send_completion_email(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send the final HR completion email.
        Supports structured parameters (name, role, team, tasks, etc.)
        or raw body content.
        """
        recipient = params.get("recipient") or params.get("to_email") or settings.HR_EMAIL
        subject = params.get("subject") or f"✅ Onboarding Completed - {params.get('name', 'Employee')}"

        # Generate text and HTML content
        plain_body = params.get("body") or params.get("email_text") or generate_email(params)
        html_body = params.get("html_body") or generate_html_email(params)

        if self.mode == "real" and not _smtp_configured():
            err_msg = "SMTP configuration missing: SMTP_HOST, SMTP_USER, and SMTP_PASSWORD are required for real email mode."
            logger.error(err_msg)
            raise ValueError(err_msg)

        result = send_email(
            to_email=recipient,
            subject=subject,
            email_text=plain_body,
            html_text=html_body,
        )
        return result

    async def send_welcome_email(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send the Day 1 welcome email to the new hire."""
        recipient = params.get("recipient") or params.get("to_email") or params.get("email")
        if not recipient:
            raise ValueError("Recipient email is required for welcome email.")

        subject = params.get("subject", "Welcome to NovaByte!")
        name = params.get("name", "Team Member")
        role = params.get("role", "Developer")

        plain_body = params.get("body") or (
            f"Hello {name},\n\n"
            f"Welcome to NovaByte as a {role}! We are thrilled to have you join our team.\n"
            f"Your onboarding supervisor agent is ready to assist you on your Day 1 journey.\n\n"
            f"Best regards,\nNovaByte Onboarding Team"
        )
        html_body = params.get("html_body") or f"""
        <div style="font-family: sans-serif; padding: 20px; color: #1f2937;">
            <h2 style="color: #1e40af;">Welcome to NovaByte, {name}! 🎉</h2>
            <p>We are thrilled to have you join us as a <strong>{role}</strong>.</p>
            <p>Your interactive onboarding assistant is active and ready to guide you through setup, repository access, and initial tasks.</p>
            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;" />
            <p style="font-size: 13px; color: #6b7280;">NovaByte Onboarding Team</p>
        </div>
        """

        if self.mode == "real" and not _smtp_configured():
            err_msg = "SMTP configuration missing: SMTP_HOST, SMTP_USER, and SMTP_PASSWORD are required for real email mode."
            logger.error(err_msg)
            raise ValueError(err_msg)

        result = send_email(
            to_email=recipient,
            subject=subject,
            email_text=plain_body,
            html_text=html_body,
        )
        return result

