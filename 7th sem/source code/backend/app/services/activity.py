from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AgentActivityDB


def record_activity(
    db: Session,
    session_id: str,
    activity_type: str,
    label: str,
    status: str,
    details: str | None = None,
) -> AgentActivityDB:
    event = AgentActivityDB(
        session_id=session_id,
        activity_type=activity_type,
        label=label,
        status=status,
        details=details,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(event)
    db.flush()
    return event


def serialize_activity(event: AgentActivityDB) -> dict[str, Any]:
    return {
        "id": event.id,
        "type": event.activity_type,
        "label": event.label,
        "status": event.status,
        "details": event.details,
        "timestamp": event.timestamp.isoformat() if event.timestamp else None,
    }
