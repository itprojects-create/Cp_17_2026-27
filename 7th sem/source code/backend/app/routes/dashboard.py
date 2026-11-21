import asyncio
from datetime import datetime, timedelta, timezone
from statistics import median

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from app.auth.utils import get_current_user, get_current_user_from_token, require_admin, websocket_auth
from app.db.database import get_db, SessionLocal
from app.db.models import UserDB, OnboardingSessionDB, ChecklistItemDB, ChatMessageDB, UserIntegrationDB
from app.integrations.manager import integration_manager
from app.services.progress import calculate_progress

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Simple connection manager for real-time integration updates
class IntegrationConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, subprotocol: str | None = None):
        await websocket.accept(subprotocol=subprotocol)
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        import json
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                pass

ws_manager = IntegrationConnectionManager()

@router.websocket("/ws/integrations")
async def websocket_endpoint(websocket: WebSocket, token: str = None):
    token, subprotocol = websocket_auth(websocket, token)
    # Verify token if provided using a scoped session to avoid connection leaks
    if not token:
        await websocket.close(code=1008)
        return

    try:
        with SessionLocal() as db:
            user = get_current_user_from_token(token, db)
            if not user:
                await websocket.close(code=1008)
                return
    except Exception:
        await websocket.close(code=1008)
        return


    await ws_manager.connect(websocket, subprotocol)
    try:
        while True:
            try:
                # Wait up to 30 seconds for a client message, then send a heartbeat ping
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send server-side heartbeat ping to keep the connection alive
                try:
                    await websocket.send_text('{"type":"ping"}')
                except Exception:
                    break
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

INTEGRATION_DEFAULTS = [
    {
        "id": "github",
        "name": "GitHub",
        "description": "Repository access, code review, and CI/CD pipeline integration.",
        "color": "bg-gray-800 dark:bg-gray-700",
    },
    {
        "id": "email",
        "name": "Email Notifications",
        "description": "Onboarding progress updates and HR completion emails.",
        "color": "bg-blue-500",
    },
]

ROADMAP_TEMPLATE = [
    {
        "id": "1",
        "title": "Account & Access Setup",
        "duration": "Day 1",
        "description": "Set up your accounts, access permissions, and security credentials.",
        "tasks": ["Create developer account", "Configure SSO & 2FA", "Set up GitHub access", "Join Slack channels"],
    },
    {
        "id": "2",
        "title": "Development Environment",
        "duration": "Day 1-2",
        "description": "Configure your local development environment with all required tools.",
        "tasks": ["Install required tools", "Clone repositories", "Configure environment variables", "Run local dev server"],
    },
    {
        "id": "3",
        "title": "Team & Culture",
        "duration": "Day 2-3",
        "description": "Meet your team, understand company culture, and learn communication norms.",
        "tasks": ["Meet your mentor", "Team introduction meeting", "Review communication guidelines", "Understand sprint workflow"],
    },
    {
        "id": "4",
        "title": "Architecture Deep Dive",
        "duration": "Day 3-5",
        "description": "Understand the system architecture, codebase structure, and technical decisions.",
        "tasks": ["Review architecture docs", "Codebase walkthrough", "Understand data flow", "Review coding standards"],
    },
    {
        "id": "5",
        "title": "First Contribution",
        "duration": "Day 5-7",
        "description": "Make your first meaningful contribution to the codebase.",
        "tasks": ["Pick a starter issue", "Write code & tests", "Submit pull request", "Address code review"],
    },
    {
        "id": "6",
        "title": "Independence & Growth",
        "duration": "Day 7-10",
        "description": "Transition to independent work and start contributing to larger features.",
        "tasks": ["Take ownership of a feature", "Participate in design review", "Mentor check-in", "Complete onboarding survey"],
    },
]


def _get_latest_session(db: Session, user_id: int):
    return (
        db.query(OnboardingSessionDB)
        .filter(OnboardingSessionDB.user_id == user_id)
        .order_by(OnboardingSessionDB.started_at.desc())
        .first()
    )


def _iso(value):
    if value is None:
        return None
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()


@router.get("/employees/{session_id}")
def get_employee_detail(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(require_admin),
):
    """Everything HR needs about one onboarding: who, how far, what evidence, which ticket, what happened."""
    import json

    from app.db.models import AgentActivityDB, UserProfileDB
    from app.routes.sessions import serialize_checklist_item
    from app.services.activity import serialize_activity

    session = db.query(OnboardingSessionDB).filter(OnboardingSessionDB.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Onboarding session not found")

    user = db.query(UserDB).filter(UserDB.id == session.user_id).first() if session.user_id else None
    profile = {}
    if user:
        row = db.query(UserProfileDB).filter(UserProfileDB.user_id == user.id).first()
        try:
            profile = json.loads(row.payload) if row else {}
        except (TypeError, ValueError):
            profile = {}

    items = db.query(ChecklistItemDB).filter(ChecklistItemDB.session_id == session_id).all()
    events = (
        db.query(AgentActivityDB)
        .filter(AgentActivityDB.session_id == session_id)
        .order_by(AgentActivityDB.timestamp.desc(), AgentActivityDB.id.desc())
        .all()
    )
    last_message = (
        db.query(ChatMessageDB.timestamp)
        .filter(ChatMessageDB.session_id == session_id, ChatMessageDB.role == "user")
        .order_by(ChatMessageDB.timestamp.desc())
        .first()
    )

    # The starter ticket is recorded as a "ticket_created" activity ("Assigned: GH-...").
    ticket_event = next((e for e in events if e.activity_type == "ticket_created"), None)
    starter_ticket = None
    if ticket_event:
        reference = (ticket_event.details or "").removeprefix("Assigned:").strip() or None
        starter_ticket = {"reference": reference, "assigned_at": _iso(ticket_event.timestamp)}

    if not user:
        account_status = "unknown"
    elif user.invited_at and not user.invite_accepted_at:
        account_status = "invite_pending"
    else:
        account_status = "active"

    last_seen = max(
        (t for t in [events[0].timestamp if events else None, last_message[0] if last_message else None] if t),
        default=None,
    )

    return {
        "employee": {
            "user_id": user.id if user else None,
            "username": user.username if user else None,
            "email": user.email if user else session.employee_email,
            "name": profile.get("name") or (user.username if user else None),
            "role": profile.get("role"),
            "years_of_experience": profile.get("years_of_experience"),
            "programming_languages": profile.get("programming_languages") or [],
            "tech_stack": profile.get("tech_stack") or [],
            "joined_at": _iso(user.created_at) if user else None,
            "invited_by": user.invited_by if user else None,
            "account_status": account_status,
        },
        "session": {
            "session_id": session.session_id,
            "status": session.status,
            "current_phase": session.current_phase,
            "persona_match": session.persona_match,
            "started_at": _iso(session.started_at),
            "completed_at": _iso(session.completed_at),
            "last_activity_at": _iso(last_seen),
        },
        "progress": calculate_progress(items),
        "checklist": [serialize_checklist_item(item) for item in items],
        "starter_ticket": starter_ticket,
        "activity": [serialize_activity(e) for e in events[:100]],
    }


@router.get("/analytics")
def get_analytics(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(require_admin),
):
    sessions = db.query(OnboardingSessionDB).all()
    session_ids = [s.session_id for s in sessions]

    checklist_items = []
    if session_ids:
        checklist_items = db.query(ChecklistItemDB).filter(ChecklistItemDB.session_id.in_(session_ids)).all()

    terminal_statuses = {"Completed", "Cancelled", "Archived"}
    active_sessions = [s for s in sessions if (s.status or "") not in terminal_statuses]
    completed_sessions = sum(1 for s in sessions if (s.status or "").lower() == "completed")
    total_sessions = len(sessions)
    completion_rate = round((completed_sessions / total_sessions) * 100, 2) if total_sessions else 0

    durations = [
        (s.completed_at - s.started_at).total_seconds() / 86400
        for s in sessions
        if s.completed_at and s.started_at
    ]
    average_onboarding_time = round(sum(durations) / len(durations), 1) if durations else None
    median_onboarding_time = round(median(durations), 1) if durations else None

    blocked = sum(1 for item in checklist_items if item.status == "Blocked")
    completed_items = [item for item in checklist_items if item.status == "Completed"]

    now = datetime.now(timezone.utc)
    # SQLite stores naive datetimes — strip tz for comparison to avoid TypeError
    now_naive = now.replace(tzinfo=None)
    weekly = []
    for week_index in range(4, -1, -1):
        start_date = now_naive - timedelta(days=(week_index + 1) * 7)
        end_date = now_naive - timedelta(days=week_index * 7)
        count = sum(
            1
            for item in completed_items
            if item.completed_at and start_date <= item.completed_at.replace(tzinfo=None) < end_date
        )
        weekly.append({"week": f"Week {5 - week_index}", "completions": count})

    dept_counts: dict[str, int] = {}
    for s in sessions:
        role = (s.persona_match or "General").split()[0]
        dept_counts[role] = dept_counts.get(role, 0) + 1

    dept = [
        {"name": role, "count": count, "color": "#6366f1"}
        for role, count in dept_counts.items()
    ]

    phase_counts: dict[str, int] = {}
    for s in sessions:
        phase = s.current_phase or "collect_info"
        phase_counts[phase] = phase_counts.get(phase, 0) + 1

    phase_breakdown = [
        {
            "phase": phase,
            "count": count,
            "pct": round((count / total_sessions) * 100, 2) if total_sessions else 0,
        }
        for phase, count in sorted(phase_counts.items())
    ]

    insights = [
        {
            "label": "Developers completed onboarding this month",
            "value": str(completed_sessions),
            "trend": None,
        },
        {
            "label": "Average time to first completed task",
            "value": f"{average_onboarding_time} days" if average_onboarding_time is not None else "No data",
            "trend": None,
        },
        {
            "label": "Tasks completed",
            "value": str(len(completed_items)),
            "trend": None,
        },
        {
            "label": "Chat interactions",
            "value": str(
                db.query(ChatMessageDB)
                .join(OnboardingSessionDB, ChatMessageDB.session_id == OnboardingSessionDB.session_id)
                .count()
            ),
            "trend": None,
        },
    ]

    return {
        "totalSessions": total_sessions,
        "completedOnboardings": completed_sessions,
        "averageOnboardingTime": average_onboarding_time,
        "medianOnboardingTime": median_onboarding_time,
        "completionRate": completion_rate,
        "activeOnboardings": len(active_sessions),
        "blockedTasks": blocked,
        "pendingVerificationTasks": sum(
            1 for item in checklist_items
            if (item.status or "").lower() in {"pending verification", "self-reported complete"}
        ),
        "weeklyCompletions": weekly,
        "departmentBreakdown": dept,
        "insights": insights,
        "phaseBreakdown": phase_breakdown,
        "definitions": {
            "totalSessions": "All persisted onboarding sessions in the authorized scope.",
            "activeOnboardings": "Sessions whose status is not Completed, Cancelled, or Archived.",
            "completionRate": "Completed sessions divided by all persisted sessions.",
            "duration": "Elapsed days between persisted started_at and completed_at timestamps.",
        },
    }


@router.get("/timeline")
def get_timeline(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    session = _get_latest_session(db, current_user.id)
    if not session:
        return {"events": []}

    items = db.query(ChecklistItemDB).filter(ChecklistItemDB.session_id == session.session_id).all()
    progress = calculate_progress(items)
    messages = (
        db.query(ChatMessageDB)
        .filter(ChatMessageDB.session_id == session.session_id)
        .order_by(ChatMessageDB.timestamp.asc())
        .all()
    )

    started_iso = session.started_at.isoformat() if session.started_at else datetime.now(timezone.utc).isoformat()
    events = [
        {
            "id": f"session-{session.session_id}",
            "title": "Account Created",
            "description": "Your developer account was set up and onboarding session started.",
            "date": started_iso,
            "completed": True,
            "kind": "account",
        }
    ]

    if messages:
        first_chat_iso = messages[0].timestamp.isoformat() if messages[0].timestamp else started_iso
        events.append(
            {
                "id": "chat-start",
                "title": "Onboarding Chat Started",
                "description": "First interaction with AI onboarding assistant.",
                "date": first_chat_iso,
                "completed": True,
                "kind": "chat",
            }
        )

    for item in items:
        events.append(
            {
                "id": item.id,
                "title": item.task,
                "description": f"Checklist task in {item.category}",
                "date": (item.completed_at.isoformat() if item.completed_at else started_iso),
                "completed": item.status == "Completed",
                "kind": "task",
            }
        )

    events.sort(key=lambda e: e["date"])
    return {"events": events, "progress": progress, "session_status": session.status}


@router.get("/roadmap")
def get_roadmap(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    session = _get_latest_session(db, current_user.id)
    if not session:
        steps = [{**s, "status": "locked"} for s in ROADMAP_TEMPLATE]
        steps[0]["status"] = "active"
        return {"steps": steps}

    items = db.query(ChecklistItemDB).filter(ChecklistItemDB.session_id == session.session_id).all()
    progress = calculate_progress(items)
    ratio = (progress["percentage"] / 100) if items else 0

    active_index = min(int(ratio * len(ROADMAP_TEMPLATE)), len(ROADMAP_TEMPLATE) - 1)
    steps = []
    for i, step in enumerate(ROADMAP_TEMPLATE):
        status = "locked"
        if i < active_index:
            status = "completed"
        elif i == active_index:
            status = "active"
        steps.append({**step, "status": status})

    return {"steps": steps, "progress": progress, "session_status": session.status, "current_phase": session.current_phase}


@router.get("/integrations")
def get_integrations(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    rows = db.query(UserIntegrationDB).filter(UserIntegrationDB.user_id == current_user.id).all()
    by_name = {r.integration: r for r in rows}

    out = []
    for item in INTEGRATION_DEFAULTS:
        row = by_name.get(item["id"])
        provider_mode = integration_manager.integrations[item["id"]].mode
        default_status = "not_configured" if provider_mode == "mock" else "disconnected"
        persisted_status = row.status if row else default_status
        # A persisted connection from a previous provider mode is not proof that
        # the currently configured provider is usable.
        if provider_mode == "mock":
            persisted_status = "not_configured"
        out.append(
            {
                **item,
                "status": persisted_status,
                "mode": provider_mode,
                "lastSync": (row.last_sync.isoformat() if row and row.last_sync else None),
            }
        )

    return {"integrations": out}


@router.post("/integrations/{integration_id}/connect")
async def connect_integration(
    integration_id: str,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    if integration_id not in integration_manager.integrations:
        raise HTTPException(status_code=404, detail="Unknown integration")

    # Broadcast sync started
    await ws_manager.broadcast({
        "type": "sync_started",
        "integration_id": integration_id
    })

    # Verify connection in real time
    is_valid = await integration_manager.verify_integration(integration_id)
    integration_mode = integration_manager.integrations[integration_id].mode
    status = "connected" if is_valid and integration_mode != "mock" else (
        "not_configured" if integration_mode == "mock" else "connection_failed"
    )
    
    row = (
        db.query(UserIntegrationDB)
        .filter(UserIntegrationDB.user_id == current_user.id, UserIntegrationDB.integration == integration_id)
        .first()
    )
    now = datetime.now(timezone.utc)

    if not row:
        row = UserIntegrationDB(user_id=current_user.id, integration=integration_id, status=status, last_sync=now)
        db.add(row)
    else:
        row.status = status
        row.last_sync = now

    db.commit()
    
    # Broadcast status change and sync completed
    await ws_manager.broadcast({
        "type": "integration_status",
        "integration_id": integration_id,
        "status": status,
        "lastSync": now.isoformat()
    })
    
    await ws_manager.broadcast({
        "type": "sync_completed",
        "integration_id": integration_id,
        "lastSync": now.isoformat()
    })
    
    return {"ok": True, "status": status}


@router.post("/integrations/sync")
async def sync_integrations(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    synced_count = 0
    
    for item in INTEGRATION_DEFAULTS:
        integration_id = item["id"]
        
        # Broadcast sync started for each
        await ws_manager.broadcast({
            "type": "sync_started",
            "integration_id": integration_id
        })

        is_valid = await integration_manager.verify_integration(integration_id)
        integration_mode = integration_manager.integrations[integration_id].mode
        status = "connected" if is_valid and integration_mode != "mock" else (
            "not_configured" if integration_mode == "mock" else "connection_failed"
        )
        
        row = (
            db.query(UserIntegrationDB)
            .filter(UserIntegrationDB.user_id == current_user.id, UserIntegrationDB.integration == integration_id)
            .first()
        )
        
        if not row:
            row = UserIntegrationDB(user_id=current_user.id, integration=integration_id, status=status, last_sync=now)
            db.add(row)
        else:
            row.status = status
            row.last_sync = now
            
        if status == "connected":
            synced_count += 1
            
        # Broadcast status change and sync completed
        await ws_manager.broadcast({
            "type": "integration_status",
            "integration_id": integration_id,
            "status": status,
            "lastSync": now.isoformat()
        })
        
        await ws_manager.broadcast({
            "type": "sync_completed",
            "integration_id": integration_id,
            "lastSync": now.isoformat()
        })

    db.commit()
    return {"ok": True, "synced": synced_count}
