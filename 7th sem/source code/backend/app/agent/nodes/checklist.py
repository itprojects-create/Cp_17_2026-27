import re
from langchain_core.messages import HumanMessage
from app.agent.tools.checklist_tools import get_checklist, get_progress, update_checklist_item
from app.db.database import SessionLocal
from app.db import models
from app.services.progress import calculate_progress, is_session_complete


STATUS_KEYWORDS = [
    ("Completed", ["complete", "completed", "done", "finished"]),
    ("In Progress", ["in progress", "started", "working on", "start"]),
    ("Blocked", ["blocked", "stuck"]),
    ("Skipped", ["skip", "skipped"]),
]


def _last_human_message(state: dict) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            return message.content.strip()
    return ""


def _detect_status(text: str) -> str | None:
    lowered = text.lower()
    for status, keywords in STATUS_KEYWORDS:
        if any(k in lowered for k in keywords):
            return status
    return None


def _detect_item_id(text: str) -> str | None:
    match = re.search(r"\b([A-Z]{1,6}-\d{1,3})\b", text, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1).upper()


def run(state: dict) -> dict:
    session_id = state.get("session_id", "")
    if not session_id:
        return {"tool_results": ["Session id missing; checklist tools not executed."]}

    text = _last_human_message(state)
    tool_results = []
    updated_item_id = None
    updated_status = None

    item_id = _detect_item_id(text)
    status = _detect_status(text)

    # If user says "complete task" without specific ID, apply to current_task_id
    if not item_id and status and state.get("current_task_id"):
        item_id = state.get("current_task_id")

    evidence = None
    completion_source = None
    if item_id and status:
        if status == "Completed":
            evidence = text
            completion_source = "user_confirmation"

        update_result = update_checklist_item.invoke(
            {
                "session_id": session_id,
                "item_id": item_id,
                "new_status": status,
                "completion_evidence": evidence,
                "completion_source": completion_source,
            }
        )
        tool_results.append(str(update_result))
        updated_item_id = item_id
        updated_status = status

    checklist_result = get_checklist.invoke({"session_id": session_id})
    progress_result = get_progress.invoke({"session_id": session_id})
    tool_results.extend([str(checklist_result), str(progress_result)])

    context_docs = "\n\n".join(tool_results)

    # Compute live progress metrics and next sequential task from DB
    completed_count = 0
    total_count = 0
    progress_percentage = 0.0
    next_task_id = None
    next_task_idx = None
    suggested_actions = []

    try:
        db = SessionLocal()
        try:
            items = db.query(models.ChecklistItemDB).filter(
                models.ChecklistItemDB.session_id == session_id
            ).all()

            if items:
                total_count = len(items)
                progress = calculate_progress(items)
                completed_count = progress["completed"]
                total_count = progress["total"]
                progress_percentage = progress["percentage"]

                # Find next pending task in sequence
                for idx, i in enumerate(items):
                    clean_id = i.id.split("::")[-1] if "::" in i.id else i.id
                    if i.status in ("Not Started", "Pending", "In Progress"):
                        next_task_id = clean_id
                        next_task_idx = idx
                        break

                if next_task_id:
                    suggested_actions.append(f"Work on next task: {next_task_id}")
                    suggested_actions.append(f"Mark {next_task_id} In Progress")
                elif is_session_complete(items):
                    suggested_actions.append("Finalize and complete onboarding")
        finally:
            db.close()
    except Exception:
        pass

    if not suggested_actions:
        suggested_actions = [
            "Review onboarding progress",
            "Ask questions about current task setup",
        ]

    return {
        "tool_results": tool_results,
        "context_docs": context_docs,
        "phase": state.get("phase", "onboarding"),
        "onboarding_status": "completed" if (total_count > 0 and completed_count == total_count) else "in_progress",
        "current_task_id": next_task_id or updated_item_id or state.get("current_task_id"),
        "current_task_index": next_task_idx if next_task_idx is not None else state.get("current_task_index", 0),
        "current_task_status": updated_status or state.get("current_task_status"),
        "completion_evidence": text if updated_status == "Completed" else state.get("completion_evidence"),
        "completion_source": "user_confirmation" if updated_status == "Completed" else state.get("completion_source"),
        "completed_count": completed_count,
        "total_count": total_count,
        "progress_percentage": progress_percentage,
        "percentage": progress_percentage,
        "suggested_actions": suggested_actions,
        "updated_item_id": updated_item_id,
        "updated_item_status": updated_status,
        "updated_item_done": updated_status == "Completed" if updated_status else None,
    }
