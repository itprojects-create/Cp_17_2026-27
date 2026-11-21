from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import List, Optional, Dict, Any


class EmployeeProfile(BaseModel):
    name: str
    email: str
    employee_id: Optional[str] = None
    role: str
    experience_level: str
    tech_stack: List[str]
    team: Optional[str] = None
    manager: Optional[str] = None
    mentor: Optional[str] = None
    start_date: Optional[str] = None


class ChecklistItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task: str
    category: str
    owner: str
    deadline: str
    status: str
    task_id: Optional[str] = None
    completion_evidence: Optional[str] = None
    completed_at: Optional[datetime] = None
    completion_source: Optional[str] = None


class OnboardingSession(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    employee: EmployeeProfile
    persona_match: str
    common_checklist: List[ChecklistItem]
    role_checklist: List[ChecklistItem]
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    current_phase: str


class SourceCitation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: str
    section: Optional[str] = None
    title: Optional[str] = None
    reference: Optional[str] = None
    context_id: Optional[str] = None
    category: Optional[str] = None
    similarity: Optional[float] = None
    score: Optional[float] = None


class ChatMessage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    role: str
    content: str
    timestamp: datetime
    metadata: Optional[Dict] = None
    sources: Optional[List[SourceCitation]] = []


class ChatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str = "assistant"
    content: str
    sources: List[SourceCitation] = []
    metadata: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    response: Optional[str] = None


class OnboardingTask(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    order: int
    title: str
    description: str
    category: str
    required: bool = True
    status: str = "Pending"
    role: str
    technology: str
    evidence_required: Optional[str] = None
    completion_evidence: Optional[str] = None
    completed_at: Optional[datetime] = None
    completion_source: Optional[str] = None


class OnboardingPlan(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan_id: str
    session_id: str
    role: str
    experience_level: str
    technology_stack: List[str]
    team: Optional[str] = None
    tasks: List[OnboardingTask]
    total_tasks: int
    created_at: datetime