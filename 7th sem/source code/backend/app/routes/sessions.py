from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db import crud
from app.services.email_generator import generate_email
from typing import Any, Dict, Optional
from datetime import datetime, timezone
import uuid
import json
import logging
import asyncio
import re
from pathlib import Path
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from app.agent.state import AgentState
from app.agent.nodes import detect_phase_transition
from app.auth.utils import get_current_user, get_current_user_from_token
from app.db.models import UserDB
from app.services.progress import calculate_progress, is_session_complete
from app.agent.nodes.composer import is_error_notice_text
from app.auth.utils import websocket_auth
from app.services.profile_status import user_profile_complete
from app.services.activity import record_activity, serialize_activity

logger = logging.getLogger(__name__)

router = APIRouter()


def serialize(obj):
    d = obj.__dict__.copy()
    d.pop("_sa_instance_state", None)
    return d


def save_email(email_content: str) -> str:
    out_dir = Path("sent_emails")
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = out_dir / f"completion_email_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt"
    filename.write_text(email_content, encoding="utf-8")
    return str(filename)


def infer_checklist_status_from_message(message: str) -> str | None:
    text = message.lower()
    if any(k in text for k in ["complete", "completed", "done", "finished"]):
        return "Completed"
    if any(k in text for k in ["in progress", "started", "starting", "working on"]):
        return "In Progress"
    if any(k in text for k in ["blocked", "stuck"]):
        return "Blocked"
    if any(k in text for k in ["skip", "skipped"]):
        return "Skipped"
    return None


def extract_checklist_item_ids(message: str) -> list[str]:
    return list(dict.fromkeys(m.upper() for m in re.findall(r"\b[A-Z]{1,6}-\d{1,3}\b", message, flags=re.IGNORECASE)))


def apply_checklist_update_from_message(db: Session, session_id: str, message: str) -> tuple[str, str] | None:
    """Best-effort fallback: update checklist when user clearly asks to change task status."""
    status = infer_checklist_status_from_message(message)
    if not status:
        return None

    candidate_ids = extract_checklist_item_ids(message)
    if not candidate_ids:
        return None

    updated_item = None
    for item_id in candidate_ids:
        updated_item = crud.update_checklist_status(
            db,
            item_id,
            status,
            session_id=session_id,
            completion_evidence=message if status == "Completed" else None,
            completion_source="user_confirmation" if status == "Completed" else None,
        )
        if updated_item:
            break

    if not updated_item:
        return None

    display_id = normalize_checklist_id(updated_item.id)
    tool_note = f"Auto tool fallback: update_checklist_item({display_id}, {status})"
    crud.create_chat_message(db, str(uuid.uuid4()), session_id, "tool", tool_note)
    return display_id, status


# Persona labels set before the user's role is known (signup, session creation).
GENERIC_PERSONA_LABELS = {None, "", "Unknown", "General Developer"}


def ensure_checklist_for_message(db: Session, session, session_id: str, message: str) -> str | None:
    """Generate the personalized plan once a persona can be inferred from the user's message."""
    if session.persona_match not in GENERIC_PERSONA_LABELS:
        return None

    from app.services.persona_matcher import identify_persona

    detected = identify_persona(message)
    from app.services.persona_matcher import FALLBACK_PERSONA

    if not detected or detected.persona_key == FALLBACK_PERSONA.persona_key:
        return None

    session.persona_match = detected.persona_key
    from app.services.plan_generator import apply_onboarding_plan
    apply_onboarding_plan(
        db,
        session_id,
        role=detected.role,
        experience_level=detected.experience_level,
        technology_stack=detected.tech_stack,
    )
    session.current_phase = "onboarding"
    db.commit()
    return detected.persona_key


PROFILE_INCOMPLETE_DETAIL = {
    "code": "PROFILE_INCOMPLETE",
    "message": "Complete your profile first; your onboarding checklist is generated from it.",
}


def require_complete_profile(db: Session, user: UserDB) -> None:
    if not user_profile_complete(db, user):
        raise HTTPException(status_code=403, detail=PROFILE_INCOMPLETE_DETAIL)


CHAT_EMPLOYEES_ONLY_DETAIL = {
    "code": "CHAT_EMPLOYEES_ONLY",
    "message": "The AI onboarding assistant is available to employees only.",
}


def require_employee_chat(user: UserDB) -> None:
    """HR admins manage onboarding from the dashboard; the assistant is for the employees being onboarded."""
    if getattr(user, "role", "employee") == "hr_admin":
        raise HTTPException(status_code=403, detail=CHAT_EMPLOYEES_ONLY_DETAIL)


def normalize_checklist_id(item_id: str) -> str:
    if "::" in item_id:
        return item_id.split("::", 1)[1]
    return item_id


def _can_access_session(session, current_user: UserDB) -> bool:
    if not session:
        return False
    if session.user_id == current_user.id:
        return True
    if getattr(current_user, "role", "employee") == "hr_admin":
        return True
    return False


# ─── Create Session ───
@router.post("/sessions")
def create_session(data: dict, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    import uuid

    session_id = data.get("session_id")
    if not session_id or crud.get_session(db, session_id):
        session_id = f"session_{uuid.uuid4().hex[:8]}"

    email = current_user.email
    persona = data.get("persona_match", "Unknown")

    session = crud.create_session(db, session_id, email, persona)
    session.user_id = current_user.id
    session.status = "In Progress"
    db.commit()

    # Trigger initial greeting
    try:
        from app.agent.graph import invoke_agent

        initial_state: AgentState = {
            "messages": [HumanMessage(content="Hello, I am ready to start my onboarding.")],
            "session_id": session_id,
            "matched_persona": session.persona_match,
            "phase": session.current_phase,
            "onboarding_complete": False,
            "tool_results": [],
            "suggested_actions": [],
            "context_docs": ""
        }

        result = invoke_agent(initial_state)

        agent_msg = result["messages"][-1].content
        new_phase = detect_phase_transition(initial_state, result)

        session.current_phase = new_phase
        db.commit()

    except Exception as e:
        logger.error(f"Agent initial error: {e}")
        agent_msg = "Welcome to NovaByte! I'm your AI onboarding assistant. Let's get started. What is your role and experience level?"
        session.current_phase = "collect_info"
        db.commit()

    agent_msg_id = str(uuid.uuid4())
    crud.create_chat_message(db, agent_msg_id, session_id, "assistant", agent_msg)

    return {"session_id": session.session_id, "message": "Session created"}


# ─── List Sessions ───
@router.get("/sessions")
def list_sessions(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    if getattr(current_user, "role", "employee") == "hr_admin":
        sessions = (
            db.query(crud.models.OnboardingSessionDB)
            .order_by(crud.models.OnboardingSessionDB.started_at.desc())
            .all()
        )
    else:
        sessions = (
            db.query(crud.models.OnboardingSessionDB)
            .filter(crud.models.OnboardingSessionDB.user_id == current_user.id)
            .order_by(crud.models.OnboardingSessionDB.started_at.desc())
            .all()
        )
    return {"sessions": _with_live_summary(db, sessions)}


def _with_live_summary(db: Session, sessions: list) -> list[dict]:
    """Add each employee's display name, role, verified progress and last activity to their sessions.

    Batched so the HR list costs a fixed number of queries however many employees there are.
    """
    from collections import defaultdict
    from sqlalchemy import func as sa_func

    session_ids = [s.session_id for s in sessions]
    user_ids = {s.user_id for s in sessions if s.user_id}
    if not session_ids:
        return []

    profiles = {}
    for row in db.query(crud.models.UserProfileDB).filter(crud.models.UserProfileDB.user_id.in_(user_ids)):
        try:
            profiles[row.user_id] = json.loads(row.payload)
        except (TypeError, ValueError):
            profiles[row.user_id] = {}
    usernames = dict(db.query(crud.models.UserDB.id, crud.models.UserDB.username).filter(crud.models.UserDB.id.in_(user_ids)))

    items_by_session = defaultdict(list)
    for item in db.query(crud.models.ChecklistItemDB).filter(crud.models.ChecklistItemDB.session_id.in_(session_ids)):
        items_by_session[item.session_id].append(item)

    last_message = dict(
        db.query(crud.models.ChatMessageDB.session_id, sa_func.max(crud.models.ChatMessageDB.timestamp))
        .filter(crud.models.ChatMessageDB.session_id.in_(session_ids), crud.models.ChatMessageDB.role == "user")
        .group_by(crud.models.ChatMessageDB.session_id)
    )
    last_event = dict(
        db.query(crud.models.AgentActivityDB.session_id, sa_func.max(crud.models.AgentActivityDB.timestamp))
        .filter(crud.models.AgentActivityDB.session_id.in_(session_ids))
        .group_by(crud.models.AgentActivityDB.session_id)
    )

    out = []
    for s in sessions:
        profile = profiles.get(s.user_id, {})
        summary = calculate_progress(items_by_session.get(s.session_id, []))
        latest = max((t for t in (last_message.get(s.session_id), last_event.get(s.session_id)) if t), default=None)
        if latest is not None and latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)  # SQLite drops the offset; values are stored in UTC
        out.append({
            **serialize(s),
            "employee_name": profile.get("name") or usernames.get(s.user_id),
            "employee_role": profile.get("role") or None,
            "progress": summary["percentage"],
            "completed_tasks": summary["completed"],
            "total_tasks": summary["total"],
            "last_activity_at": latest.isoformat() if latest else None,
        })
    return out


# ─── Get Session ───
@router.get("/sessions/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    session = crud.get_session(db, session_id)
    if not _can_access_session(session, current_user):
        raise HTTPException(status_code=404, detail="Session not found")
    return serialize(session)


# ─── Get Chat History ───
@router.get("/sessions/{session_id}/chat")
def get_chat_history(session_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    session = crud.get_session(db, session_id)
    if not _can_access_session(session, current_user):
        raise HTTPException(status_code=404, detail="Session not found")

    messages = crud.get_chat_messages(db, session_id)
    # We only return messages that the user should see (no raw tool calls)
    filtered_messages = []
    for m in messages:
        if m.role in ["user", "assistant", "notice"]:
            # If Content starts with a special prefix, it's a tool output for UI
            filtered_messages.append(serialize(m))

    return {"messages": filtered_messages}


# ─── Streaming Chat Logic ───
async def chat_stream_generator(session_id: str, content: str, db: Session):
    session = crud.get_session(db, session_id)
    if not session:
        yield json.dumps({"type": "error", "error": "Session not found"}) + "\n"
        return

    user_msg_id = str(uuid.uuid4())
    crud.create_chat_message(db, user_msg_id, session_id, "user", content)

    generated_persona = ensure_checklist_for_message(db, session, session_id, content)
    if generated_persona:
        yield f"data: {json.dumps({'type': 'checklist_generated', 'persona': generated_persona})}\n\n"

    # Fallback checklist update for explicit user commands (works even with mock LLM).
    fallback_update = apply_checklist_update_from_message(db, session_id, content)
    if fallback_update:
        item_id, new_status = fallback_update
        yield f"data: {json.dumps({'type': 'tool_call', 'name': 'update_checklist_item'})}\n\n"
        yield f"data: {json.dumps({'type': 'tool_result', 'count': 1})}\n\n"
        yield f"data: {json.dumps({'type': 'checklist_item_updated', 'item_id': item_id, 'status': new_status, 'done': new_status == 'Completed'})}\n\n"

    # 1. Fetch DB history and prepare LangChain format
    db_messages = crud.get_chat_messages(db, session_id)
    langchain_msgs = []
    for m in db_messages:
        if m.role == "user":
            langchain_msgs.append(HumanMessage(content=m.content))
        elif m.role == "assistant":
            langchain_msgs.append(AIMessage(content=m.content))
        elif m.role == "tool":
            langchain_msgs.append(ToolMessage(content=m.content, tool_call_id="none"))

    # 2. Prepare state
    from app.agent.graph import graph as compiled_graph

    initial_state: AgentState = {
        "messages": langchain_msgs,
        "session_id": session_id,
        "matched_persona": session.persona_match,
        "phase": session.current_phase,
        "onboarding_complete": session.status == "Completed",
        "tool_results": [],
        "suggested_actions": [],
        "context_docs": ""
    }

    matched_persona = session.persona_match
    latest_phase = initial_state.get("phase", session.current_phase)

    # Prepare for final database saving
    final_output = ""
    tool_usage_logs = []

    async def emit_incremental_chunks(text: str):
        """Emit progressively growing chunks so UI updates in real time."""
        words = text.split()
        if not words:
            return

        visible = ""
        for i, word in enumerate(words):
            visible = f"{visible} {word}".strip()
            # Emit every few words to balance smoothness and event volume.
            if i % 4 == 0 or i == len(words) - 1:
                yield f"data: {json.dumps({'type': 'chunk', 'content': visible})}\n\n"
                await asyncio.sleep(0.015)

    try:
        latest_sources: list[dict] = []
        recorded_activities: list[dict] = []

        def add_activity(activity: dict) -> None:
            event = record_activity(
                db,
                session_id,
                activity["type"],
                activity["label"],
                activity["status"],
                activity.get("details"),
            )
            activity["id"] = str(event.id)
            recorded_activities.append(activity)

        # Start initial activity
        init_act = {
            "id": f"act_router_{uuid.uuid4().hex[:6]}",
            "type": "intent_classification",
            "label": "Analyzing request & intent",
            "status": "running",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        add_activity(init_act)
        yield f"data: {json.dumps({'type': 'activity', 'activity': init_act})}\n\n"

        # Use graph.astream for asynchronous LangGraph execution
        async for output in compiled_graph.astream(initial_state, stream_mode="updates"):
            # Output dict looks like {"node_name": {state_update...}}
            for node_name, state_update in output.items():
                now_iso = datetime.now(timezone.utc).isoformat()

                if state_update.get("phase"):
                    latest_phase = state_update.get("phase")
                if state_update.get("structured_sources"):
                    latest_sources = state_update.get("structured_sources")

                # 1. Router Activity
                if node_name == "router":
                    intent = state_update.get("intent", "other")
                    act = {
                        "id": f"act_router_{uuid.uuid4().hex[:6]}",
                        "type": "intent_classification",
                        "label": f"Intent: {intent.replace('_', ' ').title()}",
                        "status": "completed",
                        "details": f"Routed to supervisor workflow",
                        "timestamp": now_iso,
                    }
                    add_activity(act)
                    yield f"data: {json.dumps({'type': 'activity', 'activity': act})}\n\n"

                # 2. Persona & Plan Activity
                elif node_name == "persona":
                    persona_data = state_update.get("persona") or {}
                    role = state_update.get("role") or persona_data.get("role")
                    level = state_update.get("experience_level") or persona_data.get("level")
                    if role:
                        act = {
                            "id": f"act_persona_{uuid.uuid4().hex[:6]}",
                            "type": "persona_identified",
                            "label": "Persona Identified",
                            "status": "completed",
                            "details": f"{role} ({level or 'Junior'})",
                            "timestamp": now_iso,
                        }
                        add_activity(act)
                        yield f"data: {json.dumps({'type': 'activity', 'activity': act})}\n\n"

                    if state_update.get("onboarding_plan"):
                        act = {
                            "id": f"act_plan_{uuid.uuid4().hex[:6]}",
                            "type": "plan_generated",
                            "label": "Generated Onboarding Plan",
                            "status": "completed",
                            "details": f"{len(state_update.get('onboarding_plan', []))} ordered tasks generated",
                            "timestamp": now_iso,
                        }
                        add_activity(act)
                        yield f"data: {json.dumps({'type': 'activity', 'activity': act})}\n\n"

                # 3. Knowledge Base Retrieval Activity
                elif node_name == "rag":
                    docs = state_update.get("structured_sources") or state_update.get("retrieved_documents") or []
                    act_search = {
                        "id": f"act_kb_search_{uuid.uuid4().hex[:6]}",
                        "type": "kb_search",
                        "label": "Searching Knowledge Base",
                        "status": "completed",
                        "details": f"ChromaDB semantic retrieval",
                        "timestamp": now_iso,
                    }
                    add_activity(act_search)
                    yield f"data: {json.dumps({'type': 'activity', 'activity': act_search})}\n\n"

                    if docs:
                        act_docs = {
                            "id": f"act_kb_retrieved_{uuid.uuid4().hex[:6]}",
                            "type": "kb_retrieved",
                            "label": "Retrieved Documents",
                            "status": "completed",
                            "details": f"{len(docs)} grounded reference(s) found",
                            "timestamp": now_iso,
                        }
                        add_activity(act_docs)
                        yield f"data: {json.dumps({'type': 'activity', 'activity': act_docs})}\n\n"

                # 4. Checklist & Progress Activity
                elif node_name == "checklist":
                    results = state_update.get("tool_results", [])
                    if results:
                        yield f"data: {json.dumps({'type': 'tool_result', 'count': len(results)})}\n\n"

                    updated_id = state_update.get("updated_item_id")
                    updated_status = state_update.get("updated_item_status")
                    if updated_id:
                        yield f"data: {json.dumps({'type': 'checklist_item_updated', 'item_id': updated_id, 'status': updated_status, 'done': state_update.get('updated_item_done')})}\n\n"

                    detail_msg = f"Task {updated_id} -> {updated_status}" if updated_id else f"{state_update.get('completed_count', 0)}/{state_update.get('total_count', 0)} tasks completed"
                    act = {
                        "id": f"act_chk_{uuid.uuid4().hex[:6]}",
                        "type": "checklist_update",
                        "label": "Updating Checklist",
                        "status": "completed",
                        "details": detail_msg,
                        "timestamp": now_iso,
                    }
                    add_activity(act)
                    yield f"data: {json.dumps({'type': 'activity', 'activity': act})}\n\n"

                # 5. Ticket Activity
                elif node_name == "ticket":
                    ticket_ref = state_update.get("ticket_reference", "Starter Task")
                    act = {
                        "id": f"act_tkt_{uuid.uuid4().hex[:6]}",
                        "type": "ticket_created",
                        "label": "Creating Starter Ticket",
                        "status": "completed",
                        "details": f"Assigned: {ticket_ref}",
                        "timestamp": now_iso,
                    }
                    add_activity(act)
                    yield f"data: {json.dumps({'type': 'activity', 'activity': act})}\n\n"

                # 6. Email / HR Report Activity
                elif node_name == "email":
                    results = state_update.get("tool_results", [])
                    if results:
                        yield f"data: {json.dumps({'type': 'tool_result', 'count': len(results)})}\n\n"
                    hr_status = state_update.get("hr_notification_status", "completed")
                    act = {
                        "id": f"act_email_{uuid.uuid4().hex[:6]}",
                        "type": "hr_report",
                        "label": "Preparing HR Completion Report",
                        "status": "completed" if hr_status in ("sent", "completed", "skipped") else "failed",
                        "details": f"Notification: {hr_status}",
                        "timestamp": now_iso,
                    }
                    add_activity(act)
                    yield f"data: {json.dumps({'type': 'activity', 'activity': act})}\n\n"

                # 7. Composer Response Activity
                elif node_name == "composer":
                    response_text = state_update.get("response", "")
                    if not response_text and "messages" in state_update:
                        latest_msg = state_update["messages"][-1]
                        if isinstance(latest_msg, AIMessage):
                            response_text = latest_msg.content

                    if response_text:
                        final_output = response_text
                        if is_error_notice_text(final_output):
                            yield f"data: {json.dumps({'type': 'notice', 'content': final_output})}\n\n"
                        else:
                            async for event in emit_incremental_chunks(final_output):
                                yield event


        # After graph stream finishes, use the latest streamed assistant content.
        final_content = final_output

        # Phase transitions logic
        new_phase = detect_phase_transition(initial_state, {"phase": latest_phase})

        if new_phase in {"onboarding", "first_task"} and session.current_phase not in {"onboarding", "first_task"}:
            # Just entered onboarding phase! Identify persona and assign tasks
            from app.services.persona_matcher import identify_persona

            # Identify persona from current user message first, then fall back to existing session value.
            detected = identify_persona(content)
            if detected:
                matched_persona = detected.persona_key
            
            # The agent's persona node has already persisted the personalized plan.
            if matched_persona and matched_persona != "Unknown":
                session.persona_match = matched_persona
                yield f"data: {json.dumps({'type': 'checklist_generated', 'persona': matched_persona})}\n\n"

        session.current_phase = new_phase
        db.commit()

        # Save the reply; failures are stored as notices so they are never replayed to the model.
        reply_role = "notice" if is_error_notice_text(final_content) else "assistant"
        crud.create_chat_message(
            db, str(uuid.uuid4()), session_id, reply_role, final_content
        )

        if latest_sources:
            yield f"data: {json.dumps({'type': 'sources', 'sources': latest_sources})}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'content': final_content, 'sources': latest_sources})}\n\n"

    except Exception as e:
        logger.error(f"Streaming error: {e}")
        fallback = "An error occurred while generating the response."
        crud.create_chat_message(db, str(uuid.uuid4()), session_id, "notice", fallback)
        yield f"data: {json.dumps({'type': 'error', 'content': fallback})}\n\n"


def _parse_sse_data(event_line: str) -> dict | None:
    """Translate one SSE data line into a JSON payload for WebSocket clients."""
    line = event_line.strip()
    if not line.startswith("data: "):
        return None
    payload = line[6:].strip()
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


@router.websocket("/ws/chat/{session_id}")
async def chat_ws(websocket: WebSocket, session_id: str, token: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """WebSocket chat endpoint for real-time streaming and checklist updates."""
    token, subprotocol = websocket_auth(websocket, token)
    try:
        try:
            if not token:
                raise HTTPException(status_code=401, detail="Missing token")
            current_user = get_current_user_from_token(token, db)
        except HTTPException:
            await websocket.accept(subprotocol=subprotocol)
            await websocket.send_json({"type": "error", "error": "Unauthorized"})
            await websocket.close(code=1008)
            return

        if getattr(current_user, "role", "employee") == "hr_admin":
            await websocket.accept(subprotocol=subprotocol)
            await websocket.send_json({"type": "error", "error": CHAT_EMPLOYEES_ONLY_DETAIL["message"],
                                       "code": CHAT_EMPLOYEES_ONLY_DETAIL["code"]})
            await websocket.close(code=1008)
            return

        session = crud.get_session(db, session_id)
        if not session or session.user_id != current_user.id:
            await websocket.accept(subprotocol=subprotocol)
            await websocket.send_json({"type": "error", "error": "Session not found"})
            await websocket.close(code=1008)
            return

        if not user_profile_complete(db, current_user):
            await websocket.accept(subprotocol=subprotocol)
            await websocket.send_json({"type": "error", "error": PROFILE_INCOMPLETE_DETAIL["message"],
                                       "code": PROFILE_INCOMPLETE_DETAIL["code"]})
            await websocket.close(code=1008)
            return

        await websocket.accept(subprotocol=subprotocol)

        while True:
            payload = await websocket.receive_json()
            content = (payload.get("message") or payload.get("content") or "").strip()
            if not content:
                await websocket.send_json({"type": "error", "error": "Message content is required"})
                continue

            async for event in chat_stream_generator(session_id, content, db):
                parsed = _parse_sse_data(event)
                if parsed is not None:
                    await websocket.send_json(parsed)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for session %s", session_id)
    except Exception as e:
        logger.error("WebSocket error for session %s: %s", session_id, e)
        try:
            await websocket.send_json({"type": "error", "error": "WebSocket processing error"})
        except Exception:
            pass
        try:
            await websocket.close(code=1011)
        except Exception:
            pass


@router.post("/sessions/{session_id}/chat/stream")
async def chat_stream(session_id: str, message_data: dict, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    """Streaming chat endpoint using Server-Sent Events (SSE)."""
    require_employee_chat(current_user)
    session = crud.get_session(db, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    require_complete_profile(db, current_user)
        
    content = (message_data.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message content is required")
        
    return StreamingResponse(
        chat_stream_generator(session_id, content, db), 
        media_type="text/event-stream"
    )

# ─── Legacy Chat Endpoint ───
@router.post("/sessions/{session_id}/chat")
def chat(session_id: str, message_data: dict, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    """Fallback non-streaming chat endpoint."""
    require_employee_chat(current_user)
    session = crud.get_session(db, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    require_complete_profile(db, current_user)

    content = (message_data.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message content is required")

    user_msg_id = str(uuid.uuid4())
    crud.create_chat_message(db, user_msg_id, session_id, "user", content)

    ensure_checklist_for_message(db, session, session_id, content)

    # Keep non-stream route behavior aligned with stream route.
    apply_checklist_update_from_message(db, session_id, content)

    db_messages = crud.get_chat_messages(db, session_id)
    langchain_msgs = []
    for m in db_messages:
        if m.role == "user":
            langchain_msgs.append(HumanMessage(content=m.content))
        elif m.role == "assistant":
            langchain_msgs.append(AIMessage(content=m.content))
        elif m.role == "tool":
            langchain_msgs.append(ToolMessage(content=m.content, tool_call_id="none"))

    from app.agent.graph import invoke_agent

    initial_state: AgentState = {
        "messages": langchain_msgs,
        "session_id": session_id,
        "matched_persona": session.persona_match,
        "phase": session.current_phase,
        "onboarding_complete": session.status == "Completed",
        "tool_results": [],
        "suggested_actions": [],
        "context_docs": ""
    }

    try:
        result = invoke_agent(initial_state)
        agent_msg = result["messages"][-1].content
        
        # Check phase updates
        new_phase = detect_phase_transition(initial_state, result)
        
        if new_phase in {"onboarding", "first_task"} and session.current_phase not in {"onboarding", "first_task"}:
            from app.services.persona_matcher import identify_persona
            for m in reversed(result["messages"]):
                if isinstance(m, HumanMessage):
                    p = identify_persona(m.content)
                    if p:
                        # The agent's persona node has already persisted the personalized plan.
                        session.persona_match = p.persona_key
                        break
        
        session.current_phase = new_phase
        db.commit()
    except Exception as e:
        logger.error(f"Agent error: {e}")
        agent_msg = "I encountered an error while processing your request."
        result = {}

    agent_msg_id = str(uuid.uuid4())
    reply_role = "notice" if is_error_notice_text(agent_msg) else "assistant"
    crud.create_chat_message(db, agent_msg_id, session_id, reply_role, agent_msg)

    retrieved_sources: list[dict] = []
    if "result" in locals() and isinstance(result, dict):
        raw_sources = result.get("structured_sources") or result.get("retrieved_documents") or []
        for s in raw_sources:
            if isinstance(s, dict) and s.get("source"):
                retrieved_sources.append({
                    "source": str(s.get("source")),
                    "section": s.get("section") or s.get("title") or None,
                    "title": s.get("title") or s.get("section") or str(s.get("source")),
                    "reference": s.get("reference") or (f"{s.get('source')} > {s.get('section')}" if s.get("section") else str(s.get("source"))),
                    "context_id": s.get("context_id") or f"{s.get('source')}::{s.get('section', '')}",
                    "category": s.get("category"),
                    "similarity": s.get("similarity"),
                    "score": s.get("score"),
                })

    return {
        "id": agent_msg_id,
        "role": reply_role,
        "content": agent_msg,
        "sources": retrieved_sources,
        "metadata": {"phase": session.current_phase},
        "message": agent_msg,
        "response": agent_msg,
    }


# ─── Get Checklist ───
@router.get("/sessions/{session_id}/checklist")
def get_checklist(session_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    session = crud.get_session(db, session_id)
    if not _can_access_session(session, current_user):
        raise HTTPException(status_code=404, detail="Session not found")

    items = db.query(crud.models.ChecklistItemDB).filter(
        crud.models.ChecklistItemDB.session_id == session_id
    ).all()
    return {"checklist": [serialize_checklist_item(item) for item in items]}


def serialize_checklist_item(item) -> dict:
    clean_id = normalize_checklist_id(item.id)
    return {
        "id": clean_id,
        "task_id": clean_id,
        "task": item.task,
        "title": item.task.split(":", 1)[0] if ":" in item.task else item.task,
        "description": item.task.split(":", 1)[1].strip() if ":" in item.task else "",
        "status": item.status,
        "category": item.category,
        "owner": item.owner,
        "deadline": item.deadline,
        "completion_evidence": getattr(item, "completion_evidence", None),
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        "completion_source": getattr(item, "completion_source", None),
    }


@router.get("/sessions/{session_id}/activity")
def get_activity(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    session = crud.get_session(db, session_id)
    if not _can_access_session(session, current_user):
        raise HTTPException(status_code=404, detail="Session not found")
    events = (
        db.query(crud.models.AgentActivityDB)
        .filter(crud.models.AgentActivityDB.session_id == session_id)
        .order_by(crud.models.AgentActivityDB.timestamp.asc(), crud.models.AgentActivityDB.id.asc())
        .all()
    )
    return {"activities": [serialize_activity(event) for event in events]}


# ─── Update Checklist Item ───
@router.patch("/sessions/{session_id}/checklist/{item_id}")
def update_checklist_item(session_id: str, item_id: str, data: dict, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    session = crud.get_session(db, session_id)
    if not _can_access_session(session, current_user):
        raise HTTPException(status_code=404, detail="Session not found")

    status = data.get("status")
    if not status:
        raise HTTPException(status_code=400, detail="Status is required")

    completion_evidence = data.get("completion_evidence")
    completion_source = data.get("completion_source")
    if not completion_source:
        if getattr(current_user, "role", "employee") == "hr_admin":
            completion_source = "admin_override"
        else:
            completion_source = "user_confirmation"

    try:
        item = crud.update_checklist_status(
            db,
            item_id,
            status,
            session_id=session_id,
            completion_evidence=completion_evidence,
            completion_source=completion_source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")

    record_activity(
        db,
        session_id,
        "checklist_update",
        "Checklist updated",
        "completed",
        f"Task {normalize_checklist_id(item.id)} -> {item.status}",
    )
    db.commit()

    # Add a system message to history invisible to user but acts as agent context
    sys_msg_id = str(uuid.uuid4())
    crud.create_chat_message(
        db, sys_msg_id, session_id, "tool", 
        f"Frontend UI triggered tool: update_checklist_item({normalize_checklist_id(item.id)}, {status})"
    )

    return {"message": "Checklist item updated", "item": serialize(item)}


# ─── Progress Summary ───
@router.get("/sessions/{session_id}/progress")
def get_progress(session_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    session = crud.get_session(db, session_id)
    if not _can_access_session(session, current_user):
        raise HTTPException(status_code=404, detail="Session not found")

    items = db.query(crud.models.ChecklistItemDB).filter(
        crud.models.ChecklistItemDB.session_id == session_id
    ).all()
    summary = calculate_progress(items)
    return {**summary, "completion_percentage": summary["percentage"]}


# ─── Complete Onboarding ───
@router.post("/sessions/{session_id}/complete")
def complete_onboarding(session_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    session = crud.get_session(db, session_id)
    if not _can_access_session(session, current_user):
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status == "Completed":
        return {
            "message": "Onboarding already completed",
            "email_generated": False,
        }

    items = db.query(crud.models.ChecklistItemDB).filter(
        crud.models.ChecklistItemDB.session_id == session_id
    ).all()

    if not is_session_complete(items):
        raise HTTPException(
            status_code=400,
            detail="Checklist must contain only verified completed or skipped tasks"
        )

    from app.services.email_generator import compute_confidence_score
    confidence_score = compute_confidence_score([
        {
            "done": i.status == "Completed",
            "skipped": i.status == "Skipped",
        }
        for i in items
    ])

    ticket = crud.get_session_ticket(db, session_id)

    mock_session_data = {
        "name": session.employee_email.split("@")[0].capitalize(),
        "role": session.persona_match,
        "email": session.employee_email,
        "total": len(items),
        "completed": sum(1 for i in items if i.status == "Completed"),
        "pending": 0,
        "completed_items": [i.task for i in items if i.status == "Completed"],
        "ticket": ticket,
        "confidence_score": confidence_score,
    }

    email_content = generate_email(mock_session_data)
    save_email(email_content)

    session.status = "Completed"
    session.completed_at = datetime.now(timezone.utc)
    db.commit()

    return {"message": "Onboarding completed", "email_generated": True}