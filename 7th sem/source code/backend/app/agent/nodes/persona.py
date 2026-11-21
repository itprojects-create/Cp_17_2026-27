from langchain_core.messages import HumanMessage
from app.services.persona_matcher import FALLBACK_PERSONA, identify_persona


def _last_human_message(state: dict) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            return message.content.strip()
    return ""


def run(state: dict) -> dict:
    phase = state.get("phase", "greeting")
    text = _last_human_message(state)

    if phase == "greeting" or not text:
        return {
            "phase": "collect_info",
            "onboarding_status": "pending",
            "context_docs": (
                "Start with a warm onboarding greeting, then ask the user to introduce their "
                "role, experience level, and primary tech stack."
            ),
            "suggested_actions": [
                "Share your role (backend/frontend/devops)",
                "Share your experience level",
                "Share your preferred tech stack",
            ],
        }

    persona = identify_persona(text) if text else None
    
    # Extract profile to check for missing critical fields
    from app.services.persona_matcher import extract_user_profile
    profile = extract_user_profile(text)
    
    # If persona is fallback OR critical info (like experience) is missing, stay in collect_info
    is_fallback = persona and persona.persona_key == FALLBACK_PERSONA.persona_key
    missing_experience = not profile.get("experience_level")
    
    if is_fallback or missing_experience:
        persona_payload = {
            "role": persona.role if persona else profile.get("role"),
            "level": persona.experience_level if persona else profile.get("experience_level"),
            "stack": persona.tech_stack if persona else profile.get("tech_stack"),
            "persona_id": persona.persona_key if persona else None,
        }
        
        clarification_msg = "The user's profile is incomplete. "
        if missing_experience:
            clarification_msg = "Acknowledge what you've learned, but specifically ask for their experience level (Junior/Senior/Intern) to personalize the checklist."
        else:
            clarification_msg = "The user's profile is ambiguous. Ask a concise follow-up question to confirm their level and primary stack."

        return {
            "persona": persona_payload,
            "phase": "collect_info",
            "onboarding_status": "pending",
            "needs_clarification": True,
            "context_docs": clarification_msg,
            "suggested_actions": [
                "What is your experience level?",
                "Are you a Junior, Senior, or Intern?",
                "How many years of experience do you have?",
            ],
        }

    effective_role = profile.get("role") or (persona.role if persona else "backend")
    effective_level = profile.get("experience_level") or (persona.experience_level if persona else "junior")
    effective_stack = profile.get("tech_stack") if (profile.get("tech_stack") and len(profile.get("tech_stack")) > 0) else (persona.tech_stack if persona else ["general"])

    persona_payload = {
        "role": effective_role,
        "level": effective_level,
        "stack": effective_stack,
        "persona_id": persona.persona_key if persona else "custom",
    }

    # Generate structured personalized plan
    session_id = state.get("session_id") or "default-session"
    from app.services.plan_generator import generate_onboarding_plan, persist_onboarding_plan
    plan = generate_onboarding_plan(
        role=effective_role,
        experience_level=effective_level,
        technology_stack=effective_stack,
        team=profile.get("team"),
        session_id=session_id,
    )

    plan_dicts = [t.model_dump() for t in plan.tasks]
    checklist_dicts = [
        {"id": t.task_id, "task": f"{t.title}: {t.description}", "category": t.category, "status": t.status}
        for t in plan.tasks
    ]

    # Persist plan to SQLite database for stateful continuity
    if session_id and session_id != "default-session":
        try:
            from app.db.database import SessionLocal
            db = SessionLocal()
            try:
                persist_onboarding_plan(db, session_id, plan)
            finally:
                db.close()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Plan persistence notice: %s", exc)

    first_task_id = plan.tasks[0].task_id if plan.tasks else None
    first_task_status = plan.tasks[0].status if plan.tasks else "Pending"

    return {
        "persona": persona_payload,
        "matched_persona": persona.persona_key if persona else "custom",
        "name": profile.get("name") or state.get("name"),
        "role": effective_role,
        "experience_level": effective_level,
        "technology_stack": effective_stack,
        "team": profile.get("team") or f"{effective_role.capitalize()} Engineering",
        "phase": "onboarding",
        "onboarding_status": "in_progress",
        "onboarding_plan": plan_dicts,
        "checklist": checklist_dicts,
        "current_task_id": first_task_id,
        "current_task_index": 0,
        "current_step_index": 0,
        "current_task_status": first_task_status,
        "total_count": len(plan.tasks),
        "completed_count": 0,
        "progress_percentage": 0.0,
        "suggested_actions": [
            f"Start Task 1: {plan.tasks[0].title}" if plan.tasks else "Review checklist",
            "Review your generated checklist",
            "Ask questions about architecture or standards",
        ],
    }
