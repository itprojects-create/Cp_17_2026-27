"""Independent verification of checklist mutations produced by the agent."""
from app.db.database import SessionLocal
from app.db import models


def run(state: dict) -> dict:
    session_id = state.get("session_id")
    item_id = state.get("updated_item_id")
    requested_status = state.get("updated_item_status")
    if not session_id or not item_id:
        return {
            "verification_result": {"verified": True, "reason": "No mutation to verify"},
            "tool_call_status": "success",
        }

    db = SessionLocal()
    try:
        item = db.query(models.ChecklistItemDB).filter(
            models.ChecklistItemDB.session_id == session_id,
            (models.ChecklistItemDB.id == item_id)
            | (models.ChecklistItemDB.id == f"{session_id}::{item_id}"),
        ).first()
        verified = bool(
            item
            and item.status == requested_status
            and (
                item.status != "Completed"
                or (item.completion_evidence and item.completion_source and item.completed_at)
            )
        )
        reason = "Persisted checklist state matches the requested transition" if verified else (
            "Checklist transition was not persisted with required verification evidence"
        )
        return {
            "verification_result": {"verified": verified, "reason": reason},
            "tool_call_status": "success" if verified else "failed",
            "failure_reason": None if verified else reason,
        }
    finally:
        db.close()
