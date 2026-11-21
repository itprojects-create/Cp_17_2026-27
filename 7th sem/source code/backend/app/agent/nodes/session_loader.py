"""
Session loader node for the onboarding supervisor workflow.
Rehydrates state from SQLite database (session, persona, plan, active task, progress).
"""
import logging
from typing import Dict, Any
from app.db.database import SessionLocal
from app.db import models
from app.services.plan_generator import get_plan_tasks_for_session
from app.services.persona_matcher import load_personas, FALLBACK_PERSONA

logger = logging.getLogger(__name__)


def _persona_state(persona_key: str) -> Dict[str, Any]:
    """
    Persona fields for a stored persona key, in the shape the persona node emits.
    Graph state is rebuilt every turn, so without this the RAG node would only get
    persona-aware retrieval on the single turn where the user introduced themselves.
    """
    candidates = [FALLBACK_PERSONA]
    try:
        candidates += load_personas()
    except Exception as exc:
        logger.debug("Persona catalogue unavailable: %s", exc)
    persona = next((p for p in candidates if p.persona_key == persona_key), None)
    if not persona:
        return {}
    return {
        "persona": {
            "role": persona.role,
            "level": persona.experience_level,
            "stack": persona.tech_stack,
            "persona_id": persona.persona_key,
        },
        "role": persona.role.lower(),
        "experience_level": persona.experience_level.lower(),
        "technology_stack": persona.tech_stack,
    }


def run(state: dict) -> dict:
    """
    Load and rehydrate session state from database for persistent, resumable onboarding.
    """
    session_id = state.get("session_id")
    if not session_id or session_id == "default-session":
        return {}

    updates: Dict[str, Any] = {}

    try:
        db = SessionLocal()
        try:
            # 1. Check existing session record
            session_db = db.query(models.OnboardingSessionDB).filter(
                models.OnboardingSessionDB.session_id == session_id
            ).first()

            if session_db:
                if session_db.persona_match and not state.get("matched_persona"):
                    updates["matched_persona"] = session_db.persona_match
                if session_db.persona_match and not state.get("persona"):
                    updates.update(_persona_state(session_db.persona_match))
                if session_db.status == "Completed" or session_db.current_phase == "completed":
                    updates["onboarding_complete"] = True
                    updates["onboarding_status"] = "completed"
                    updates["phase"] = "completed"
                    updates["current_phase"] = "completed"

            # 2. Check persisted checklist items / plan
            tasks = get_plan_tasks_for_session(db, session_id)
            if tasks:
                updates["checklist"] = tasks
                updates["onboarding_plan"] = tasks
                total = len(tasks)
                completed = sum(1 for t in tasks if t.get("status") in ("Completed", "Skipped"))
                updates["total_count"] = total
                updates["completed_count"] = completed
                updates["progress_percentage"] = round((completed / total) * 100, 1) if total > 0 else 0.0

                # Determine active current task
                current_active = None
                current_idx = None
                for idx, t in enumerate(tasks):
                    if t.get("status") in ("Not Started", "Pending", "In Progress"):
                        current_active = t.get("task_id")
                        current_idx = idx
                        break

                if current_active:
                    updates["current_task_id"] = current_active
                    updates["current_task_index"] = current_idx
                    updates["current_task_status"] = tasks[current_idx].get("status", "Pending")

                if total > 0 and completed == total:
                    updates["onboarding_complete"] = True
                    updates["onboarding_status"] = "completed"

        finally:
            db.close()
    except Exception as exc:
        logger.warning("Session loader rehydration warning: %s", exc)

    return updates
