import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.utils import get_current_user
from app.db.database import get_db
from app.db.models import UserDB, UserSettingsDB
from app.agent.llm_loader import check_llm_health, get_llm_provider_info

router = APIRouter(prefix="/settings", tags=["settings"])
system_router = APIRouter(prefix="/system", tags=["system"])


@system_router.get("/llm-status")
def get_system_llm_status(check: bool = False):
    """
    Active LLM provider, model and configuration status.
    With `?check=true`, also sends each configured model a tiny request and reports
    `health` ("ok" / "failing" / "unavailable"), cached for a minute.
    """
    return check_llm_health() if check else get_llm_provider_info()


@router.get("/llm-status")
def get_settings_llm_status():
    """Get the current active LLM provider, model, and status."""
    return get_llm_provider_info()


DEFAULT_SETTINGS = {
    "emailNotifications": True,
    "checklistReminders": True,
    "securityAlerts": True,
    "weeklyDigest": False,
    "autoStartLastSession": True,
    "compactSidebar": False,
    "timezone": "Asia/Kolkata",
}


class SettingsPayload(BaseModel):
    emailNotifications: bool
    checklistReminders: bool
    securityAlerts: bool
    weeklyDigest: bool
    autoStartLastSession: bool
    compactSidebar: bool
    timezone: str


def _read_user_settings(db: Session, user_id: int) -> dict:
    row = db.query(UserSettingsDB).filter(UserSettingsDB.user_id == user_id).first()
    if not row:
        return DEFAULT_SETTINGS.copy()

    try:
        data = json.loads(row.payload)
    except Exception:
        data = {}

    merged = DEFAULT_SETTINGS.copy()
    merged.update({k: v for k, v in data.items() if k in merged})
    return merged


@router.get("")
def get_settings(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    return _read_user_settings(db, current_user.id)


@router.put("")
def update_settings(
    payload: SettingsPayload,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    data = payload.model_dump()
    row = db.query(UserSettingsDB).filter(UserSettingsDB.user_id == current_user.id).first()

    if not row:
        row = UserSettingsDB(user_id=current_user.id, payload=json.dumps(data))
        db.add(row)
    else:
        row.payload = json.dumps(data)

    db.commit()

    return data
