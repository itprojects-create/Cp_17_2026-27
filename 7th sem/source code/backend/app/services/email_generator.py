import os
import html
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr, formatdate, make_msgid
from datetime import datetime, timezone
from app.config import settings

logger = logging.getLogger(__name__)

# Find backend folder dynamically
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
TEMPLATE_PATH = os.path.join(BASE_DIR, "templates", "email_templates.md")


def compute_confidence_score(checklist: list[dict]) -> float:
    total = len(checklist)
    if total == 0:
        return 0.0

    completed = sum(1 for item in checklist if item.get("done") or item.get("status") == "Completed")
    skipped = sum(1 for item in checklist if item.get("skipped") or item.get("status") == "Skipped")
    score = (completed - 0.5 * skipped) / total * 100
    return round(max(score, 0.0), 1)


DEFAULT_EMAIL_TEMPLATE = """Subject: Onboarding Completed - {name}

Employee Details
Name: {name}
Role: {role}
Email: {email}
Team: {team}
Experience Level: {experience_level}
Technology Stack: {tech_stack}

Timeline
Onboarding Start Time: {start_time}
Completion Time: {completion_time}

Checklist Summary
Total Tasks: {total}
Completed: {completed}
Pending: {pending}
Overall Progress: {progress}%
Completed Items: {completed_items}
Pending Items: {pending_items}
Confidence Score: {confidence_score}%
Verification Info: {verification_info}

Starter Ticket
Ticket ID: {ticket}

Generated At: {time}"""


def load_template() -> str:
    """
    Reads the email template file or falls back to inline template.
    """
    try:
        if os.path.exists(TEMPLATE_PATH):
            with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
                return f.read()
    except Exception as e:
        logger.warning("Failed reading email template: %s", e)
    return DEFAULT_EMAIL_TEMPLATE


def generate_email(data: dict) -> str:
    """
    Generates the plain-text final completion email with all required metadata fields.
    """
    template = load_template()

    name = data.get("name") or "New Team Member"
    role = data.get("role") or "Developer"
    email_addr = data.get("email") or "N/A"
    team = data.get("team") or "Engineering"
    experience_level = data.get("experience_level") or data.get("level") or "Junior"

    tech_stack = data.get("tech_stack") or data.get("technology_stack") or []
    if isinstance(tech_stack, list):
        tech_stack_str = ", ".join(str(t) for t in tech_stack) if tech_stack else "General"
    else:
        tech_stack_str = str(tech_stack or "General")

    start_time = data.get("started_at") or data.get("start_time") or "N/A"
    completion_time = data.get("completed_at") or data.get("completion_time") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    total = str(data.get("total", 0))
    completed = str(data.get("completed", 0))
    pending = str(data.get("pending", 0))
    progress = str(data.get("progress") or data.get("progress_percentage") or ("100" if int(pending) == 0 and int(total) > 0 else "0"))

    ticket = str(data.get("ticket") or data.get("ticket_reference") or "N/A")
    confidence_score = str(data.get("confidence_score", "100.0"))
    verification_info = str(data.get("verification_info") or data.get("completion_source") or "Verified via automated onboarding workflow")

    completed_items = data.get("completed_items") or data.get("completed_tasks") or []
    if isinstance(completed_items, list):
        completed_items_text = ", ".join(str(item.get("task") if isinstance(item, dict) else item) for item in completed_items) if completed_items else "None"
    else:
        completed_items_text = str(completed_items or "None")

    pending_items = data.get("pending_items") or data.get("pending_tasks") or []
    if isinstance(pending_items, list):
        pending_items_text = ", ".join(str(item.get("task") if isinstance(item, dict) else item) for item in pending_items) if pending_items else "None"
    else:
        pending_items_text = str(pending_items or "None")

    time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    email = template
    email = email.replace("{name}", str(name))
    email = email.replace("{role}", str(role))
    email = email.replace("{email}", str(email_addr))
    email = email.replace("{team}", str(team))
    email = email.replace("{experience_level}", str(experience_level))
    email = email.replace("{tech_stack}", tech_stack_str)
    email = email.replace("{start_time}", str(start_time))
    email = email.replace("{completion_time}", str(completion_time))
    email = email.replace("{total}", total)
    email = email.replace("{completed}", completed)
    email = email.replace("{pending}", pending)
    email = email.replace("{progress}", progress)
    email = email.replace("{completed_items}", completed_items_text)
    email = email.replace("{pending_items}", pending_items_text)
    email = email.replace("{ticket}", ticket)
    email = email.replace("{confidence_score}", confidence_score)
    email = email.replace("{verification_info}", verification_info)
    email = email.replace("{time}", time_str)

    return email


def generate_html_email(data: dict) -> str:
    """
    Generates a professional, responsive HTML completion email with styled cards,
    badges, structured details table, and checklist verification breakdown.
    """
    name = html.escape(str(data.get("name") or "New Team Member"))
    role = html.escape(str(data.get("role") or "Developer"))
    email_addr = html.escape(str(data.get("email") or "N/A"))
    team = html.escape(str(data.get("team") or "Engineering"))
    experience_level = html.escape(str(data.get("experience_level") or data.get("level") or "Junior").title())

    tech_stack = data.get("tech_stack") or data.get("technology_stack") or []
    if isinstance(tech_stack, list):
        tech_stack_str = html.escape(", ".join(str(t) for t in tech_stack) if tech_stack else "General")
    else:
        tech_stack_str = html.escape(str(tech_stack or "General"))

    start_time = html.escape(str(data.get("started_at") or data.get("start_time") or "N/A"))
    completion_time = html.escape(str(data.get("completed_at") or data.get("completion_time") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")))

    total = int(data.get("total", 0))
    completed = int(data.get("completed", 0))
    pending = int(data.get("pending", max(0, total - completed)))
    pct = data.get("progress") or data.get("progress_percentage") or (100 if pending == 0 and total > 0 else (round((completed / total) * 100) if total > 0 else 0))

    ticket = html.escape(str(data.get("ticket") or data.get("ticket_reference") or "N/A"))
    confidence_score = html.escape(str(data.get("confidence_score", "100.0")))
    verification_info = html.escape(str(data.get("verification_info") or data.get("completion_source") or "Automated Onboarding Workflow"))

    completed_items = data.get("completed_items") or data.get("completed_tasks") or []
    completed_rows = ""
    if isinstance(completed_items, list) and completed_items:
        for itm in completed_items:
            task_title = itm.get("task") if isinstance(itm, dict) else str(itm)
            evidence = itm.get("completion_evidence") if isinstance(itm, dict) else None
            evidence_html = f"<div style='font-size: 12px; color: #6b7280; margin-top: 2px;'>Evidence: {html.escape(str(evidence))}</div>" if evidence else ""
            completed_rows += f"""
            <li style='padding: 8px 0; border-bottom: 1px solid #f3f4f6; list-style: none;'>
                <span style='color: #16a34a; font-weight: bold; margin-right: 6px;'>✓</span>
                <span style='color: #1f2937; font-weight: 500;'>{html.escape(task_title)}</span>
                {evidence_html}
            </li>
            """
    else:
        completed_rows = "<li style='padding: 8px 0; color: #6b7280; list-style: none;'>No completed tasks recorded.</li>"

    pending_items = data.get("pending_items") or data.get("pending_tasks") or []
    pending_rows = ""
    if isinstance(pending_items, list) and pending_items:
        for itm in pending_items:
            task_title = itm.get("task") if isinstance(itm, dict) else str(itm)
            pending_rows += f"""
            <li style='padding: 6px 0; border-bottom: 1px solid #f3f4f6; list-style: none;'>
                <span style='color: #eab308; font-weight: bold; margin-right: 6px;'>⏳</span>
                <span style='color: #4b5563;'>{html.escape(task_title)}</span>
            </li>
            """
    else:
        pending_rows = "<li style='padding: 6px 0; color: #16a34a; font-weight: 500; list-style: none;'>🎉 None — All required tasks completed!</li>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Onboarding Completed - {name}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f3f4f6; margin: 0; padding: 24px; color: #1f2937; line-height: 1.5;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width: 640px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 16px rgba(0,0,0,0.06); border: 1px solid #e5e7eb;">
    <!-- Header -->
    <tr>
      <td style="background: linear-gradient(135deg, #1e40af, #3b82f6); padding: 32px 24px; text-align: center; color: #ffffff;">
        <h1 style="margin: 0 0 6px 0; font-size: 22px; font-weight: 700; letter-spacing: -0.5px;">NovaByte AI Onboarding</h1>
        <p style="margin: 0; font-size: 15px; opacity: 0.95;">Employee Onboarding Milestone Completed</p>
        <div style="margin-top: 14px;">
          <span style="background-color: #dcfce7; color: #15803d; padding: 6px 14px; border-radius: 9999px; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">✓ Onboarding Complete ({pct}%)</span>
        </div>
      </td>
    </tr>

    <!-- Body Content -->
    <tr>
      <td style="padding: 28px 24px;">
        
        <!-- Employee Profile Section -->
        <div style="background-color: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 18px; margin-bottom: 20px;">
          <h2 style="font-size: 13px; font-weight: 700; text-transform: uppercase; color: #6b7280; letter-spacing: 0.5px; margin: 0 0 12px 0;">👤 Employee Profile</h2>
          <table width="100%" style="font-size: 14px; border-collapse: collapse;">
            <tr>
              <td style="padding: 5px 0; color: #6b7280; width: 38%;">Name:</td>
              <td style="padding: 5px 0; color: #111827; font-weight: 600;">{name}</td>
            </tr>
            <tr>
              <td style="padding: 5px 0; color: #6b7280;">Email:</td>
              <td style="padding: 5px 0; color: #111827; font-weight: 600;"><a href="mailto:{email_addr}" style="color: #2563eb; text-decoration: none;">{email_addr}</a></td>
            </tr>
            <tr>
              <td style="padding: 5px 0; color: #6b7280;">Role & Seniority:</td>
              <td style="padding: 5px 0; color: #111827; font-weight: 600;">{role} ({experience_level})</td>
            </tr>
            <tr>
              <td style="padding: 5px 0; color: #6b7280;">Assigned Team:</td>
              <td style="padding: 5px 0; color: #111827; font-weight: 600;">{team}</td>
            </tr>
            <tr>
              <td style="padding: 5px 0; color: #6b7280;">Technology Stack:</td>
              <td style="padding: 5px 0; color: #111827; font-weight: 600;">{tech_stack_str}</td>
            </tr>
          </table>
        </div>

        <!-- Onboarding Progress & Metrics -->
        <div style="background-color: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 18px; margin-bottom: 20px;">
          <h2 style="font-size: 13px; font-weight: 700; text-transform: uppercase; color: #6b7280; letter-spacing: 0.5px; margin: 0 0 12px 0;">📊 Checklist Progress & Timeline</h2>
          <table width="100%" style="font-size: 14px; border-collapse: collapse;">
            <tr>
              <td style="padding: 5px 0; color: #6b7280; width: 38%;">Started At:</td>
              <td style="padding: 5px 0; color: #111827; font-weight: 500;">{start_time}</td>
            </tr>
            <tr>
              <td style="padding: 5px 0; color: #6b7280;">Completed At:</td>
              <td style="padding: 5px 0; color: #111827; font-weight: 500;">{completion_time}</td>
            </tr>
            <tr>
              <td style="padding: 5px 0; color: #6b7280;">Tasks Completed:</td>
              <td style="padding: 5px 0; color: #111827; font-weight: 700;">{completed} of {total} ({pct}%)</td>
            </tr>
            <tr>
              <td style="padding: 5px 0; color: #6b7280;">Starter Ticket:</td>
              <td style="padding: 5px 0; color: #1e40af; font-weight: 700;">{ticket}</td>
            </tr>
            <tr>
              <td style="padding: 5px 0; color: #6b7280;">Confidence Score:</td>
              <td style="padding: 5px 0; color: #16a34a; font-weight: 700;">{confidence_score}%</td>
            </tr>
            <tr>
              <td style="padding: 5px 0; color: #6b7280;">Verification Status:</td>
              <td style="padding: 5px 0; color: #4b5563;">{verification_info}</td>
            </tr>
          </table>
        </div>

        <!-- Completed Tasks Breakdown -->
        <div style="background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 18px; margin-bottom: 20px;">
          <h2 style="font-size: 13px; font-weight: 700; text-transform: uppercase; color: #15803d; letter-spacing: 0.5px; margin: 0 0 10px 0;">✓ Completed Tasks ({completed})</h2>
          <ul style="margin: 0; padding: 0;">
            {completed_rows}
          </ul>
        </div>

        <!-- Pending Tasks Breakdown -->
        <div style="background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 18px; margin-bottom: 20px;">
          <h2 style="font-size: 13px; font-weight: 700; text-transform: uppercase; color: #b45309; letter-spacing: 0.5px; margin: 0 0 10px 0;">⏳ Pending Tasks ({pending})</h2>
          <ul style="margin: 0; padding: 0;">
            {pending_rows}
          </ul>
        </div>

      </td>
    </tr>

    <!-- Footer -->
    <tr>
      <td style="background-color: #f9fafb; padding: 18px 24px; text-align: center; font-size: 12px; color: #9ca3af; border-top: 1px solid #e5e7eb;">
        <p style="margin: 0 0 4px 0;">Automated notification generated by NovaByte Autonomous Onboarding Agent.</p>
        <p style="margin: 0;">Please contact <a href="mailto:{settings.HR_EMAIL}" style="color: #6b7280; text-decoration: underline;">{settings.HR_EMAIL}</a> for queries.</p>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def smtp_connection():
    """Open an authenticated SMTP connection (SSL on port 465 or SMTP_USE_SSL, otherwise STARTTLS)."""
    host, port = settings.SMTP_HOST, int(settings.SMTP_PORT)
    if settings.SMTP_USE_SSL or port == 465:
        server = smtplib.SMTP_SSL(host, port, timeout=15)
    else:
        server = smtplib.SMTP(host, port, timeout=15)
        server.ehlo()
        if settings.SMTP_USE_TLS:
            server.starttls()
            server.ehlo()
    try:
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
    except Exception:
        server.close()
        raise
    return server


def verify_smtp_connection() -> tuple[bool, str | None]:
    """Log in to the SMTP server without sending anything. Returns (ok, reason)."""
    if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        return False, "SMTP_HOST, SMTP_USER and SMTP_PASSWORD must all be set"
    try:
        smtp_connection().quit()
        return True, None
    except Exception as e:
        return False, describe_smtp_error(e)


def describe_smtp_error(e: Exception) -> str:
    """Turn common SMTP failures into an actionable message."""
    if isinstance(e, smtplib.SMTPAuthenticationError):
        hint = (" For Gmail, use a 16-character App Password (Google Account > Security > 2-Step Verification > "
                "App passwords), not your normal password.") if "gmail" in settings.SMTP_HOST.lower() else ""
        return f"login rejected by {settings.SMTP_HOST}.{hint}"
    if isinstance(e, smtplib.SMTPSenderRefused):
        return f"sender address {settings.SMTP_FROM_EMAIL} was refused; it must be your account or a verified alias."
    if isinstance(e, smtplib.SMTPRecipientsRefused):
        return "recipient address was refused by the server."
    if isinstance(e, (TimeoutError, OSError)) and not isinstance(e, smtplib.SMTPException):
        return f"could not reach {settings.SMTP_HOST}:{settings.SMTP_PORT} ({e}). Check host, port and firewall."
    return str(e)


def send_email(to_email: str, subject: str, email_text: str, html_text: str | None = None) -> dict:
    """
    Sends the email using SMTP in 'real' mode or persists to sent_emails in 'mock' mode.
    Never reports success if real SMTP delivery fails.
    """
    mode = getattr(settings, "EMAIL_MODE", "mock").lower().strip()

    # Mock mode
    if mode != "real":
        logger.info("[MOCK EMAIL SEND] To: %s | Subject: %s", to_email, subject)
        save_dir = getattr(settings, "BASE_DIR", BASE_DIR) / "sent_emails" if hasattr(settings, "BASE_DIR") else os.path.join(BASE_DIR, "sent_emails")
        os.makedirs(str(save_dir), exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(str(save_dir), f"completion_email_{timestamp}.html")
        content_to_save = html_text or f"<!-- To: {to_email} -->\n<!-- Subject: {subject} -->\n<pre>{html.escape(email_text)}</pre>"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content_to_save)
        logger.info("Mock email saved to: %s", file_path)
        return {"status": "success", "mode": "mock", "file": str(file_path)}

    # Real SMTP mode
    if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        err_msg = "SMTP configuration missing: SMTP_HOST, SMTP_USER, and SMTP_PASSWORD are required for real email mode."
        logger.error(err_msg)
        raise ValueError(err_msg)

    from_email = settings.SMTP_FROM_EMAIL or settings.SMTP_USER
    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr((settings.SMTP_FROM_NAME, from_email)) if settings.SMTP_FROM_NAME else from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    # Date and Message-ID are required by RFC 5322; mail without them is routinely marked as spam.
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=from_email.split("@")[-1] if "@" in from_email else None)
    msg.attach(MIMEText(email_text, "plain", "utf-8"))
    if html_text:
        msg.attach(MIMEText(html_text, "html", "utf-8"))

    try:
        server = smtp_connection()
        try:
            server.send_message(msg)
        finally:
            server.quit()
        logger.info("Successfully sent real SMTP email to %s", to_email)
        return {"status": "success", "mode": "real", "recipient": to_email}
    except Exception as e:
        logger.error("Failed to send real SMTP email to %s: %s", to_email, e)
        raise RuntimeError(f"SMTP delivery failed: {describe_smtp_error(e)}") from e
