from typing import Optional
import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _get_db():
    from app.db.database import SessionLocal
    return SessionLocal()


@tool
def get_checklist(session_id: str) -> str:
    """Return formatted checklist items for a given onboarding session."""
    try:
        db = _get_db()
        from app.db import models
        items = db.query(models.ChecklistItemDB).filter(
            models.ChecklistItemDB.session_id == session_id
        ).all()
        db.close()

        if not items:
            return "No checklist items found. The checklist may not have been generated yet."

        result = "📋 **Current Onboarding Checklist:**\n\n"
        for item in items:
            display_id = item.id.split("::", 1)[1] if "::" in item.id else item.id
            status_emoji = {
                "Not Started": "⬜",
                "Pending": "⏳",
                "In Progress": "🔄",
                "Completed": "✅",
                "Blocked": "🚫",
                "Skipped": "⏭️",
            }.get(item.status, "⬜")
            evidence_str = f" [Evidence: {item.completion_evidence}]" if item.completion_evidence else ""
            result += f"{status_emoji} **{display_id}**: {item.task} — *{item.status}*{evidence_str}\n"

        return result
    except Exception as e:
        logger.error("get_checklist error: %s", e)
        return f"Error retrieving checklist: {str(e)}"


@tool
def update_checklist_item(
    session_id: str,
    item_id: str,
    new_status: str,
    completion_evidence: Optional[str] = None,
    completion_source: Optional[str] = None,
) -> str:
    """Update one checklist item's status for a given session with evidence and source."""
    valid_statuses = [
        "Not Started",
        "Pending",
        "In Progress",
        "Pending Verification",
        "Self-Reported Complete",
        "Completed",
        "Blocked",
        "Skipped",
    ]
    if new_status not in valid_statuses:
        return f"Invalid status. Must be one of: {', '.join(valid_statuses)}"

    try:
        db = _get_db()
        from app.db import models
        from app.db.crud import update_checklist_status
        existing = db.query(models.ChecklistItemDB).filter(
            models.ChecklistItemDB.session_id == session_id,
            (models.ChecklistItemDB.id == item_id)
            | (models.ChecklistItemDB.id == f"{session_id}::{item_id}"),
        ).first()
        previous_status = existing.status if existing else None
        item = update_checklist_status(
            db,
            item_id,
            new_status,
            session_id=session_id,
            completion_evidence=completion_evidence,
            completion_source=completion_source,
        )
        if not item:
            db.close()
            return f"Could not find checklist item with ID '{item_id}'."
        display_id = item.id.split("::", 1)[1] if "::" in item.id else item.id
        task_text = item.task
        item_status = item.status
        item_source = item.completion_source
        if item and item.status != previous_status:
            from app.services.activity import record_activity

            record_activity(
                db,
                session_id,
                "checklist_update",
                "Checklist updated",
                "completed",
                f"Task {item.id.split('::', 1)[-1]} -> {item.status}",
            )
            db.commit()
        db.close()

        evidence_info = f" (Evidence: {completion_evidence})" if completion_evidence else ""
        source_info = f" [Source: {item_source}]" if item_source else ""
        return f"✅ Task **{display_id}** ({task_text}) has been updated to **{item_status}**{evidence_info}{source_info}."
    except ValueError as e:
        logger.info("Rejected checklist transition for %s: %s", item_id, e)
        return f"Checklist update rejected: {e}"
    except Exception as e:
        logger.error("update_checklist_item error: %s", e)
        return f"Error updating task: {str(e)}"


@tool
def get_progress(session_id: str) -> str:
    """Return onboarding progress summary percentages for a session."""
    try:
        db = _get_db()
        from app.db import models
        items = db.query(models.ChecklistItemDB).filter(
            models.ChecklistItemDB.session_id == session_id
        ).all()
        db.close()

        if not items:
            return "No checklist items found for this session."

        total = len(items)
        from app.services.progress import calculate_progress

        summary = calculate_progress(items)
        completed = summary["completed"]
        in_progress = sum(1 for i in items if i.status == "In Progress")
        blocked = sum(1 for i in items if i.status == "Blocked")
        not_started = sum(1 for i in items if i.status in ("Not Started", "Pending"))
        pct = summary["percentage"]

        next_task = next((i for i in items if i.status == "Not Started"), None)

        result = (
            f"📊 **Onboarding Progress: {pct}%**\n\n"
            f"- ✅ Completed: {completed}/{total}\n"
            f"- 🔄 In Progress: {in_progress}\n"
            f"- ⬜ Not Started: {not_started}\n"
            f"- 🚫 Blocked: {blocked}\n"
        )

        if next_task:
            result += f"\n**🎯 Recommended Next Task:** {next_task.id} — {next_task.task}"

        if pct == 100:
            result += "\n\n🎉 **All tasks complete!** Ready to finalize onboarding."

        return result
    except Exception as e:
        logger.error("get_progress error: %s", e)
        return f"Error getting progress: {str(e)}"
