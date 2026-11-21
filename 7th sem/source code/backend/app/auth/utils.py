from datetime import datetime, timedelta, timezone
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import UserDB
from app.config import settings

# Security configurations
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

# Use pbkdf2 for better compatibility with Python 3.14
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    return get_current_user_from_token(token, db)


def get_current_user_from_token(token: str, db: Session) -> UserDB:
    """Resolve an authenticated user from a raw JWT token string."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(UserDB).filter(UserDB.username == username).first()
    if user is None:
        raise credentials_exception
    return user


def require_admin(current_user: UserDB = Depends(get_current_user)) -> UserDB:
    """Dependency to enforce that current user has hr_admin role."""
    if getattr(current_user, "role", "employee") != "hr_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user



# Browsers can't set headers on a WebSocket, but they can offer subprotocols, which travel in
# the Sec-WebSocket-Protocol header. Clients send ["novabyte.bearer", <jwt>] so the token never
# appears in the URL (and therefore never in access logs or proxy logs).
WS_AUTH_SUBPROTOCOL = "novabyte.bearer"


def websocket_auth(websocket: WebSocket, query_token: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
    """Return (token, subprotocol to accept). Falls back to the legacy `?token=` query parameter."""
    offered = [p.strip() for p in websocket.headers.get("sec-websocket-protocol", "").split(",") if p.strip()]
    if WS_AUTH_SUBPROTOCOL in offered:
        index = offered.index(WS_AUTH_SUBPROTOCOL)
        token = offered[index + 1] if index + 1 < len(offered) else None
        return token, WS_AUTH_SUBPROTOCOL
    return query_token, None
