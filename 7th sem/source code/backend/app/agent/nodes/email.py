from datetime import datetime, timezone
import logging
from app.agent.tools.email_tools import generate_hr_email

logger = logging.getLogger(__name__)


def run(state: dict) -> dict:
    session_id = state.get("session_id", "")
    now_iso = datetime.now(timezone.utc).isoformat()
    if not session_id:
        return {
            "tool_results": ["Session ID missing; email summary not generated."],
            "onboarding_complete": True,
            "onboarding_status": "completed",
            "phase": "completed",
            "current_phase": "completed",
            "completion_timestamp": now_iso,
            "hr_notification_status": "skipped",
        }

    try:
        summary = generate_hr_email.invoke({"session_id": session_id})
        tool_msg = str(summary)
        hr_status = "sent" if "successfully" in tool_msg.lower() or "mock" in tool_msg.lower() or "saved" in tool_msg.lower() else "failed"
    except Exception as e:
        logger.error(f"Error generating HR onboarding completion email: {e}")
        tool_msg = (
            "Onboarding completed successfully. Automatic HR email notification encountered "
            "an issue and will be reviewed manually by the HR team."
        )
        hr_status = "error"

    return {
        "tool_results": [tool_msg],
        "onboarding_complete": True,
        "onboarding_status": "completed",
        "phase": "completed",
        "current_phase": "completed",
        "completion_timestamp": now_iso,
        "hr_notification_status": hr_status,
    }
