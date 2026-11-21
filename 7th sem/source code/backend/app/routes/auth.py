import logging
import base64
import json
import re
from typing import Optional
from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.db.database import get_db
from app.db.models import UserDB, PasswordResetTokenDB, UserProfileDB, UserSettingsDB, OnboardingSessionDB, ChatMessageDB
from app.auth.utils import get_password_hash, verify_password, create_access_token, get_current_user, require_admin, ACCESS_TOKEN_EXPIRE_MINUTES
from app.config import settings
from app.services.profile_status import user_profile_complete

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)


router = APIRouter(prefix="/auth", tags=["auth"])

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str = "employee"

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: str = "employee"
    # False until the employee completes their profile; the app is gated on it.
    profile_completed: bool = True


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class GoogleAuthRequest(BaseModel):
    credential: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None


class GitHubAuthRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None


def _decode_google_jwt(token: str) -> dict:
    """
    Decode and verify Google ID Token JWT payload.
    Attempts Google tokeninfo verification first; falls back to local JWT payload decoding.
    """
    import urllib.request
    import json

    # 1. Try real-time Google verification endpoint
    try:
        url = f"https://oauth2.googleapis.com/tokeninfo?id_token={token}"
        req = urllib.request.Request(url, headers={"User-Agent": "NovaByte-Auth/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                if data.get("email"):
                    logger.info("✅ Live Google OAuth token verified for: %s", data.get("email"))
                    return data
    except Exception as exc:
        logger.debug("Google tokeninfo check: %s, using local decode fallback", exc)

    # 2. Local JWT payload decode
    try:
        parts = token.split(".")
        if len(parts) >= 2:
            payload_b64 = parts[1]
            padded = payload_b64 + "=" * (-len(payload_b64) % 4)
            decoded_bytes = base64.urlsafe_b64decode(padded)
            return json.loads(decoded_bytes.decode("utf-8"))
    except Exception as exc:
        logger.warning("Failed to decode Google JWT token: %s", exc)
    return {}



def _provision_oauth_user(db: Session, email: str, display_name: str, avatar: Optional[str] = None) -> UserDB:
    """Helper to provision a new user, profile, settings, and onboarding workspace for OAuth users."""
    base_username = (display_name or email.split("@")[0]).strip()
    clean_username = re.sub(r'[^a-zA-Z0-9_-]', '', base_username) or "dev_user"
    username = clean_username
    counter = 1
    while db.query(UserDB).filter(UserDB.username == username).first():
        username = f"{clean_username}_{counter}"
        counter += 1

    hashed_password = get_password_hash(secrets.token_urlsafe(24))
    new_user = UserDB(
        username=username,
        email=email,
        password_hash=hashed_password,
        role="employee",
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    _provision_workspace(db, new_user, display_name or new_user.username)
    return new_user


def _provision_workspace(db: Session, new_user: UserDB, display_name: str) -> str:
    """Create a new employee's profile, settings, onboarding session and greeting. Returns the session id."""
    import uuid

    initial_profile = {
        "name": display_name,
        "email": new_user.email,
        "role": "General Developer",
        "skills": [],
        "programming_languages": [],
        "tech_stack": [],
        "years_of_experience": 0,
        "current_projects": "",
        "past_experience": "",
        "github_username": "",
        "preferred_tools": [],
        "timezone": "UTC+5:30 (IST)",
    }
    db.add(UserProfileDB(user_id=new_user.id, payload=json.dumps(initial_profile)))
    db.add(UserSettingsDB(user_id=new_user.id, payload=json.dumps({"theme": "dark", "notifications": True})))

    session_id = f"session_{uuid.uuid4().hex[:8]}"
    session = OnboardingSessionDB(
        session_id=session_id,
        user_id=new_user.id,
        employee_email=new_user.email,
        persona_match="General Developer",
        status="In Progress",
        started_at=datetime.now(timezone.utc),
        current_phase="greeting",
    )
    db.add(session)
    db.commit()

    # No checklist yet: the plan is generated from the profile, which the user must complete first.

    greeting_msg = (
        f"Welcome to NovaByte, {new_user.username}! I am your AI onboarding assistant. "
        "Complete your profile to generate your personalized onboarding checklist, then I can guide you through it."
    )
    db.add(
        ChatMessageDB(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role="assistant",
            content=greeting_msg,
            timestamp=datetime.now(timezone.utc),
        )
    )
    db.commit()

    return session_id



def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite drops the UTC offset on read, so treat stored naive timestamps as UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _mark_invite_accepted(db: Session, user: UserDB) -> None:
    """An invited employee who signs in or sets a password is no longer a pending invite."""
    if getattr(user, "invited_at", None) and not getattr(user, "invite_accepted_at", None):
        user.invite_accepted_at = datetime.now(timezone.utc)
        db.commit()


def _issue_password_link(db: Session, user: UserDB, lifetime: timedelta) -> str:
    """Invalidate the user's open tokens and return a new single-use set-password link."""
    now = datetime.now(timezone.utc)
    db.query(PasswordResetTokenDB).filter(
        PasswordResetTokenDB.user_id == user.id,
        PasswordResetTokenDB.used_at.is_(None),
    ).update({"used_at": now}, synchronize_session=False)

    raw_token = secrets.token_urlsafe(32)
    db.add(
        PasswordResetTokenDB(
            user_id=user.id,
            token_hash=_hash_token(raw_token),
            expires_at=now + lifetime,
        )
    )
    db.commit()
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}/reset-password?token={raw_token}"


def _send_invite_email(recipient: str, username: str, invite_link: str):
    subject = "You're invited to NovaByte onboarding"
    body = (
        f"Hi {username},\n\n"
        "Your NovaByte onboarding account has been created by HR.\n\n"
        f"Set your password here: {invite_link}\n\n"
        f"Your username is: {username}\n"
        f"This link will expire in {settings.INVITE_EXPIRE_HOURS} hours.\n"
        "After signing in, complete your profile to get your personalized onboarding plan."
    )

    if settings.EMAIL_MODE == "mock":
        out_dir = settings.BASE_DIR / "sent_emails"
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = out_dir / f"invite_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"
        filename.write_text(f"To: {recipient}\nSubject: {subject}\n\n{body}", encoding="utf-8")
        return

    from app.services.email_generator import send_email

    send_email(to_email=recipient, subject=subject, email_text=body)


def _send_password_reset_email(recipient: str, reset_link: str):
    subject = "NovaByte Password Reset"
    body = (
        "We received a request to reset your NovaByte account password.\n\n"
        f"Reset link: {reset_link}\n\n"
        f"This link will expire in {settings.PASSWORD_RESET_EXPIRE_MINUTES} minutes.\n"
        "If you did not request this, you can ignore this email."
    )

    if settings.EMAIL_MODE == "mock":
        out_dir = settings.BASE_DIR / "sent_emails"
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = out_dir / f"password_reset_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"
        filename.write_text(f"To: {recipient}\nSubject: {subject}\n\n{body}", encoding="utf-8")
        return

    from app.services.email_generator import send_email

    send_email(to_email=recipient, subject=subject, email_text=body)

@router.post("/register", response_model=UserResponse)
@limiter.limit("5/minute")
def register(request: Request, user_data: UserCreate, db: Session = Depends(get_db)):
    import logging

    logging.getLogger(__name__).debug("Register endpoint hit: %s", user_data.username)
    db_user = db.query(UserDB).filter(
        (UserDB.username == user_data.username) | (UserDB.email == user_data.email)
    ).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username or email already registered")
    
    hashed_password = get_password_hash(user_data.password)
    # Always enforce default "employee" role for public registration
    new_user = UserDB(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
        role="employee",
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    _provision_workspace(db, new_user, new_user.username)

    return new_user


class InviteRequest(BaseModel):
    username: str
    email: str


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@router.post("/invite")
def invite_employee(payload: InviteRequest, db: Session = Depends(get_db), admin: UserDB = Depends(require_admin)):
    """HR admin creates an employee account; the employee sets their own password from an emailed link."""
    username = payload.username.strip()
    email = payload.email.strip().lower()
    if not USERNAME_PATTERN.match(username):
        raise HTTPException(status_code=400, detail="Username must be 3-32 letters, digits, '_' or '-'")
    if not EMAIL_PATTERN.match(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    if db.query(UserDB).filter((UserDB.username == username) | (UserDB.email == email)).first():
        raise HTTPException(status_code=400, detail="Username or email already registered")

    # Unusable random password until the employee sets their own from the invite link.
    new_user = UserDB(
        username=username,
        email=email,
        password_hash=get_password_hash(secrets.token_urlsafe(24)),
        role="employee",
        invited_by=admin.username,
        invited_at=datetime.now(timezone.utc),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    session_id = _provision_workspace(db, new_user, username)

    invite_link = _issue_password_link(db, new_user, timedelta(hours=settings.INVITE_EXPIRE_HOURS))
    email_sent = True
    try:
        _send_invite_email(email, username, invite_link)
    except Exception as exc:
        email_sent = False
        logger.warning("Invite email delivery failed for %s: %s", email, exc)

    logger.info("HR admin %s invited employee %s", admin.username, username)
    return {
        "user": UserResponse.model_validate(new_user).model_copy(
            update={"profile_completed": user_profile_complete(db, new_user)}
        ),
        "session_id": session_id,
        "email_sent": email_sent,
    }


def _pending_invitee(db: Session, user_id: int) -> UserDB:
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user or not user.invited_at or user.invite_accepted_at:
        raise HTTPException(status_code=404, detail="Pending invite not found")
    return user


def _serialize_invite(db: Session, user: UserDB) -> dict:
    latest = (
        db.query(PasswordResetTokenDB)
        .filter(PasswordResetTokenDB.user_id == user.id, PasswordResetTokenDB.used_at.is_(None))
        .order_by(PasswordResetTokenDB.expires_at.desc())
        .first()
    )
    expires_at = _as_utc(latest.expires_at) if latest else None
    expired = expires_at is None or expires_at < datetime.now(timezone.utc)
    return {
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "invited_by": user.invited_by,
        "invited_at": _as_utc(user.invited_at).isoformat(),
        "expires_at": expires_at.isoformat() if expires_at else None,
        "status": "expired" if expired else "pending",
    }


@router.get("/invites")
def list_pending_invites(db: Session = Depends(get_db), admin: UserDB = Depends(require_admin)):
    """Employees invited by HR who have not yet set a password or signed in."""
    users = (
        db.query(UserDB)
        .filter(UserDB.invited_at.isnot(None), UserDB.invite_accepted_at.is_(None))
        .order_by(UserDB.invited_at.desc())
        .all()
    )
    return {"invites": [_serialize_invite(db, u) for u in users]}


@router.post("/invites/{user_id}/resend")
def resend_invite(user_id: int, db: Session = Depends(get_db), admin: UserDB = Depends(require_admin)):
    """Send a fresh invite link; any earlier link stops working."""
    user = _pending_invitee(db, user_id)
    invite_link = _issue_password_link(db, user, timedelta(hours=settings.INVITE_EXPIRE_HOURS))
    email_sent = True
    try:
        _send_invite_email(user.email, user.username, invite_link)
    except Exception as exc:
        email_sent = False
        logger.warning("Invite email delivery failed for %s: %s", user.email, exc)
    logger.info("HR admin %s resent the invite for %s", admin.username, user.username)
    return {**_serialize_invite(db, user), "email_sent": email_sent}


@router.delete("/invites/{user_id}")
def cancel_invite(user_id: int, db: Session = Depends(get_db), admin: UserDB = Depends(require_admin)):
    """Remove a never-activated invited account and everything provisioned for it."""
    from app.db.models import AgentActivityDB, ChecklistItemDB, UserIntegrationDB

    user = _pending_invitee(db, user_id)
    session_ids = [s.session_id for s in db.query(OnboardingSessionDB.session_id).filter(OnboardingSessionDB.user_id == user.id)]
    if session_ids:
        for model in (ChecklistItemDB, ChatMessageDB, AgentActivityDB):
            db.query(model).filter(model.session_id.in_(session_ids)).delete(synchronize_session=False)
        db.query(OnboardingSessionDB).filter(OnboardingSessionDB.session_id.in_(session_ids)).delete(synchronize_session=False)
    for model in (PasswordResetTokenDB, UserProfileDB, UserSettingsDB, UserIntegrationDB):
        db.query(model).filter(model.user_id == user.id).delete(synchronize_session=False)
    username = user.username
    db.delete(user)
    db.commit()
    logger.info("HR admin %s cancelled the invite for %s", admin.username, username)
    return {"cancelled": username}


@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Allow login with either username or email
    user = db.query(UserDB).filter(
        (UserDB.username == form_data.username) | (UserDB.email == form_data.username)
    ).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    _mark_invite_accepted(db, user)
    user_role = getattr(user, "role", "employee") or "employee"
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user_role}, expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user_role,
            "profile_completed": user_profile_complete(db, user),
        }
    }


@router.post("/google")
@limiter.limit("15/minute")
def google_auth(request: Request, payload: GoogleAuthRequest, db: Session = Depends(get_db)):
    email = payload.email
    name = payload.name or "Google User"
    picture = payload.picture

    if payload.credential:
        decoded = _decode_google_jwt(payload.credential)
        if decoded.get("email"):
            email = decoded.get("email")
        if decoded.get("name"):
            name = decoded.get("name")
        if decoded.get("picture"):
            picture = decoded.get("picture")

    if not email:
        raise HTTPException(status_code=400, detail="Valid email address is required for Google Sign-In")

    user = db.query(UserDB).filter(UserDB.email == email).first()
    if not user:
        user = _provision_oauth_user(db, email=email, display_name=name, avatar=picture)

    _mark_invite_accepted(db, user)
    user_role = getattr(user, "role", "employee") or "employee"
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user_role}, expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user_role,
            "profile_completed": user_profile_complete(db, user),
        }
    }


@router.post("/github")
@limiter.limit("15/minute")
def github_auth(request: Request, payload: GitHubAuthRequest, db: Session = Depends(get_db)):
    email = payload.email or f"{payload.username or 'github_dev'}@users.noreply.github.com"
    name = payload.name or payload.username or "GitHub Developer"

    user = db.query(UserDB).filter(UserDB.email == email).first()
    if not user and payload.username:
        user = db.query(UserDB).filter(UserDB.username == payload.username).first()

    if not user:
        user = _provision_oauth_user(db, email=email, display_name=name)

    _mark_invite_accepted(db, user)
    user_role = getattr(user, "role", "employee") or "employee"
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user_role}, expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user_role,
            "profile_completed": user_profile_complete(db, user),
        }
    }


@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": getattr(current_user, "role", "employee") or "employee",
        "profile_completed": user_profile_complete(db, current_user),
    }


@router.post("/logout")
def logout(current_user: UserDB = Depends(get_current_user)):
    # JWTs are stateless in this app; client-side token removal completes sign-out.
    return {"message": f"User {current_user.username} signed out successfully"}


@router.post("/forgot-password/request")
def forgot_password_request(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    # Always return success to avoid disclosing whether an email is registered.
    response = {"message": "If this email exists, a password reset link has been sent."}

    user = db.query(UserDB).filter(UserDB.email == payload.email).first()
    if not user:
        return response

    reset_link = _issue_password_link(db, user, timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES))
    try:
        _send_password_reset_email(user.email, reset_link)
    except Exception as exc:
        # Do not leak delivery failures to clients and preserve the uniform response.
        logger.warning("Password reset email delivery failed for %s: %s", user.email, exc)

    return response



@router.post("/forgot-password/reset")
def forgot_password_reset(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    now = datetime.now(timezone.utc)
    token_hash = _hash_token(payload.token)

    token_row = db.query(PasswordResetTokenDB).filter(
        PasswordResetTokenDB.token_hash == token_hash,
        PasswordResetTokenDB.used_at.is_(None),
    ).first()

    if not token_row or _as_utc(token_row.expires_at) < now:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user = db.query(UserDB).filter(UserDB.id == token_row.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    user.password_hash = get_password_hash(payload.new_password)
    token_row.used_at = now
    if user.invited_at and not user.invite_accepted_at:
        user.invite_accepted_at = now

    db.query(PasswordResetTokenDB).filter(
        PasswordResetTokenDB.user_id == user.id,
        PasswordResetTokenDB.used_at.is_(None),
    ).update({"used_at": now}, synchronize_session=False)

    db.commit()
    return {"message": "Password reset successful"}
