"""
Typed state definitions for the autonomous onboarding LangGraph workflow.

Supports full statefulness across:
1. Employee / Persona representation
2. Onboarding Task Plan
3. Current Task tracking & completion evidence
4. Agent Execution tracing (intents, documents, tool outputs)
5. Progress metrics & status
6. Completion metadata & HR notification tracking
"""
from typing import TypedDict, Annotated, List, Optional, Literal, Dict, Any
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class TaskPlanItem(TypedDict, total=False):
    """Structured representation of an onboarding task item."""
    task_id: str
    id: str
    title: str
    task: str
    category: str
    owner: str
    deadline: str
    is_required: bool
    required: bool
    status: Literal["Pending", "In Progress", "Completed", "Blocked", "Skipped"]
    order: int
    completion_evidence: Optional[str]
    completed_at: Optional[str]
    completion_source: Optional[str]


class EmployeePersonaState(TypedDict, total=False):
    """Detailed employee and matched persona state."""
    name: Optional[str]
    email: Optional[str]
    role: Optional[str]
    experience_level: Optional[str]
    technology_stack: Optional[List[str]]
    team: Optional[str]
    persona_key: Optional[str]
    persona_id: Optional[str]
    level: Optional[str]
    stack: Optional[List[str]]


class AgentState(TypedDict, total=False):
    """
    Comprehensive state for the autonomous onboarding agent workflow.
    Fully backward-compatible with all existing LangGraph nodes, tools, and session managers.
    """
    # LangGraph conversational message stream
    messages: Annotated[List[BaseMessage], add_messages]

    # Session & Identity Context
    session_id: str
    user_id: Optional[int]
    user_email: Optional[str]

    # =========================================================================
    # 1. Employee / Persona
    # =========================================================================
    name: Optional[str]
    role: Optional[str]
    experience_level: Optional[str]
    technology_stack: Optional[List[str]]
    team: Optional[str]
    matched_persona: Optional[str]
    persona: Optional[Dict[str, Any]]
    needs_clarification: Optional[bool]

    # =========================================================================
    # 2. Onboarding Plan
    # =========================================================================
    onboarding_plan: Optional[List[Dict[str, Any]]]
    checklist: List[Dict[str, Any]]

    # =========================================================================
    # 3. Current Task & Evidence
    # =========================================================================
    current_task_id: Optional[str]
    current_task_index: Optional[int]
    current_step_index: int
    current_task_status: Optional[str]
    completion_evidence: Optional[str]
    completion_source: Optional[str]
    updated_item_id: Optional[str]
    updated_item_status: Optional[str]
    updated_item_done: Optional[bool]

    # =========================================================================
    # 4. Agent Execution Tracing
    # =========================================================================
    phase: Literal["greeting", "collect_info", "first_task", "onboarding", "completed"]
    current_phase: Optional[str]
    intent: Literal["greeting", "intro", "question", "checklist_action", "complete", "other"]
    detected_intent: Optional[str]
    retrieved_chunks: List[str]
    retrieved_sources: List[str]
    sources: Optional[List[str]]
    retrieved_documents: Optional[List[Dict[str, Any]]]
    structured_sources: Optional[List[Dict[str, Any]]]
    context_docs: str
    tool_results: List[str]
    tool_call_status: Optional[str]
    verification_result: Optional[Dict[str, Any]]
    failure_reason: Optional[str]
    retry_count: int
    max_retries: int
    suggested_actions: List[str]
    response: str

    # =========================================================================
    # 5. Progress Metrics
    # =========================================================================
    completed_count: Optional[int]
    total_count: Optional[int]
    progress_percentage: Optional[float]
    percentage: Optional[float]
    onboarding_status: Literal["pending", "in_progress", "completed"]

    # =========================================================================
    # 6. Completion & Integrations
    # =========================================================================
    onboarding_complete: bool
    completion_timestamp: Optional[str]
    hr_notification_status: Optional[str]
    ticket_assigned: bool
    ticket_reference: Optional[str]
