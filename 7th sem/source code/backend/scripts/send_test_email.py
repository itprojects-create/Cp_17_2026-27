"""
Check the SMTP settings in backend/.env and send one test email.

Usage (from backend/):
    python scripts/send_test_email.py you@example.com
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.services.email_generator import send_email, verify_smtp_connection  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2 or "@" not in sys.argv[1]:
        print(__doc__)
        return 2
    recipient = sys.argv[1]

    print(f"EMAIL_MODE : {settings.EMAIL_MODE}")
    print(f"Server     : {settings.SMTP_HOST}:{settings.SMTP_PORT} "
          f"({'SSL' if settings.SMTP_USE_SSL or settings.SMTP_PORT == 465 else 'STARTTLS' if settings.SMTP_USE_TLS else 'plain'})")
    print(f"Login      : {settings.SMTP_USER or '<not set>'}")
    print(f"From       : {settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>")
    print(f"HR_EMAIL   : {settings.HR_EMAIL}\n")

    if settings.EMAIL_MODE != "real":
        print("EMAIL_MODE is not 'real', so the app is writing emails to backend/sent_emails/ instead of sending them.")
        print("Set EMAIL_MODE=real in backend/.env to send real email.")
        return 1

    print("1/2 Logging in ...", end=" ", flush=True)
    ok, reason = verify_smtp_connection()
    if not ok:
        print(f"FAILED\n    {reason}")
        return 1
    print("ok")

    print(f"2/2 Sending a test email to {recipient} ...", end=" ", flush=True)
    try:
        send_email(
            to_email=recipient,
            subject="NovaByte test email",
            email_text="This is a test email from your NovaByte onboarding app. SMTP is configured correctly.",
            html_text="<p>This is a test email from your <strong>NovaByte</strong> onboarding app.</p>"
                      "<p>SMTP is configured correctly. &#9989;</p>",
        )
    except Exception as e:
        print(f"FAILED\n    {e}")
        return 1
    print("sent")
    print("\nCheck the inbox (and the spam folder) of", recipient)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
