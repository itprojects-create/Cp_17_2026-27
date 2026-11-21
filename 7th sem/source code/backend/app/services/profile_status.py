"""
When is an employee's profile complete enough to generate their onboarding plan?

The plan is chosen from the role and tech stack, so both are required. Completion is
derived from the stored profile (no separate flag), which keeps existing users correct.
"""
import json
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import UserDB, UserProfileDB

PROFILE_ROLES = ["Frontend", "Backend", "DevOps", "ML", "Fullstack"]


def missing_profile_fields(profile: Optional[dict]) -> list[str]:
    """Human-readable names of the required fields that are still missing."""
    profile = profile or {}
    missing = []
    if str(profile.get("role") or "").strip().lower() not in {r.lower() for r in PROFILE_ROLES}:
        missing.append("role")
    if not (profile.get("tech_stack") or profile.get("programming_languages")):
        missing.append("tech stack or programming languages")
    return missing


def is_profile_complete(profile: Optional[dict]) -> bool:
    return not missing_profile_fields(profile)


def user_profile_complete(db: Session, user: UserDB) -> bool:
    """HR admins have no onboarding plan, so the requirement only applies to employees."""
    if getattr(user, "role", "employee") == "hr_admin":
        return True
    row = db.query(UserProfileDB).filter(UserProfileDB.user_id == user.id).first()
    if not row:
        return False
    try:
        return is_profile_complete(json.loads(row.payload))
    except (TypeError, ValueError):
        return False
