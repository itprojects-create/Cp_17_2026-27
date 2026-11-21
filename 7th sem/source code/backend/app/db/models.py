from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base

class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String, default="employee", nullable=False)
    created_at = Column(DateTime, default=func.now())
    # Set when an HR admin creates the account; accepted once the employee sets a password.
    invited_by = Column(String, nullable=True)
    invited_at = Column(DateTime, nullable=True)
    invite_accepted_at = Column(DateTime, nullable=True)

    sessions = relationship("OnboardingSessionDB", back_populates="user")
    settings = relationship("UserSettingsDB", back_populates="user", uselist=False)
    profile = relationship("UserProfileDB", back_populates="user", uselist=False)
    integrations = relationship("UserIntegrationDB", back_populates="user")
    password_reset_tokens = relationship("PasswordResetTokenDB", back_populates="user")


class UserSettingsDB(Base):
    __tablename__ = "user_settings"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    payload = Column(Text, nullable=False, default="{}")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    user = relationship("UserDB", back_populates="settings")


class UserProfileDB(Base):
    __tablename__ = "user_profiles"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    payload = Column(Text, nullable=False, default="{}")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    user = relationship("UserDB", back_populates="profile")


class UserIntegrationDB(Base):
    __tablename__ = "user_integrations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    integration = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="disconnected")
    last_sync = Column(DateTime, nullable=True)

    user = relationship("UserDB", back_populates="integrations")


class PasswordResetTokenDB(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())

    user = relationship("UserDB", back_populates="password_reset_tokens")


class OnboardingSessionDB(Base):
    __tablename__ = "onboarding_sessions"

    session_id = Column(String, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True) # nullable for backward compatibility
    employee_email = Column(String)
    persona_match = Column(String)
    status = Column(String)
    started_at = Column(DateTime)
    completed_at = Column(DateTime, nullable=True)
    current_phase = Column(String)

    user = relationship("UserDB", back_populates="sessions")


class ChecklistItemDB(Base):
    __tablename__ = "checklist_items"

    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, index=True)
    task = Column(String)
    category = Column(String)
    owner = Column(String)
    deadline = Column(String)
    status = Column(String)
    completion_evidence = Column(Text, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    completion_source = Column(String, nullable=True)


class ChatMessageDB(Base):
    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, index=True)
    role = Column(String)
    content = Column(Text)
    timestamp = Column(DateTime)


class AgentActivityDB(Base):
    __tablename__ = "agent_activity_events"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("onboarding_sessions.session_id"), nullable=False, index=True)
    activity_type = Column(String, nullable=False)
    label = Column(String, nullable=False)
    status = Column(String, nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=func.now(), index=True)