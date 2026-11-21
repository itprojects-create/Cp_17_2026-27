import logging
from langchain_core.tools import tool
from app.config import settings

logger = logging.getLogger(__name__)


def _get_db():
    from app.db.database import SessionLocal
    return SessionLocal()


def _confidence_for_items(items) -> float:
    from app.services.email_generator import compute_confidence_score

    payload = []
    for item in items:
        payload.append({
            "done": item.status == "Completed",
            "skipped": item.status == "Skipped",
        })
    return compute_confidence_score(payload)


@tool
def generate_hr_email(session_id: str) -> str:
    """Generate and send an HR completion email when onboarding is complete."""
    try:
        db = _get_db()
        from app.db import models, crud

        session = crud.get_session(db, session_id)
        items = db.query(models.ChecklistItemDB).filter(
            models.ChecklistItemDB.session_id == session_id
        ).all()
        db.close()

        if not session:
            return "Session not found."

        total = len(items)
        completed = sum(1 for i in items if i.status == "Completed")
        confidence_score = _confidence_for_items(items)

        summary = (
            f"📧 **Onboarding Completion Summary**\n\n"
            f"- **Employee:** {session.employee_email}\n"
            f"- **Role:** {session.persona_match}\n"
            f"- **Tasks Completed:** {completed}/{total}\n"
            f"- **Confidence Score:** {confidence_score}%\n"
            f"- **Status:** {'✅ Complete' if completed == total else '⏳ In Progress'}\n\n"
        )

        if completed == total:
            try:
                from datetime import datetime, timezone
                from app.services.email_generator import generate_email, generate_html_email, send_email

                # Extract persona details if stored on session or fallback gracefully
                persona_data = getattr(session, "persona", {}) or {}
                if not isinstance(persona_data, dict):
                    persona_data = {}

                name = session.employee_name if hasattr(session, "employee_name") and session.employee_name else session.employee_email.split('@')[0].replace('.', ' ').title()
                role = session.persona_match or persona_data.get("role") or "Developer"
                team = persona_data.get("team") or "Engineering"
                experience_level = persona_data.get("experience_level") or persona_data.get("level") or "Junior"
                tech_stack = persona_data.get("tech_stack") or persona_data.get("technology_stack") or []

                completed_tasks = [
                    {
                        "task": item.task,
                        "completion_evidence": getattr(item, "completion_evidence", None),
                        "completed_at": str(getattr(item, "completed_at", "")),
                        "completion_source": getattr(item, "completion_source", "automated_verification"),
                    }
                    for item in items if item.status == "Completed"
                ]

                pending_tasks = [
                    {
                        "task": item.task,
                        "status": item.status,
                    }
                    for item in items if item.status != "Completed"
                ]

                start_time_str = str(getattr(session, "created_at", "") or "N/A")
                completion_time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

                email_data = {
                    "name": name,
                    "role": role,
                    "email": session.employee_email,
                    "team": team,
                    "experience_level": experience_level,
                    "tech_stack": tech_stack,
                    "start_time": start_time_str,
                    "completion_time": completion_time_str,
                    "total": total,
                    "completed": completed,
                    "pending": total - completed,
                    "progress": 100,
                    "completed_items": completed_tasks,
                    "pending_items": pending_tasks,
                    "ticket": f"ONB-{session_id.replace('session_', '')}",
                    "confidence_score": confidence_score,
                    "verification_info": "Verified via evidence-aware checklist and automated workflow",
                }

                email_text = generate_email(email_data)
                html_text = generate_html_email(email_data)

                send_email(
                    to_email=settings.HR_EMAIL,
                    subject=f"✅ Onboarding Completed: {email_data['name']}",
                    email_text=email_text,
                    html_text=html_text,
                )
                summary += "All onboarding tasks have been completed. An HR notification email has been sent successfully."
            except Exception as e:
                logger.error("Failed to send HR email: %s", e)
                summary += f"All onboarding tasks were completed, but failed to send HR email: {e}"
        else:
            remaining = total - completed
            summary += f"Onboarding is {round((completed / total) * 100) if total else 0}% complete. {remaining} tasks remaining."

        return summary
    except Exception as e:
        logger.error("generate_hr_email error: %s", e)
        return f"Error generating summary: {str(e)}"

