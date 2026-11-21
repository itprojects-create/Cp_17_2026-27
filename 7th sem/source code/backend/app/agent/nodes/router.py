import re
from langchain_core.messages import HumanMessage
from app.services.persona_matcher import identify_persona, FALLBACK_PERSONA


def _last_human_message(state: dict) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            return message.content.strip()
    return ""


TASK_ID_PATTERN = r"\b[A-Z]{1,6}-\d{1,3}\b"
QUESTION_STARTS = (
    "what", "how", "where", "why", "when", "who", "which", "can ", "could ", "should ",
    "is ", "are ", "do ", "does ", "tell me", "explain",
)
SELF_INTRO_PHRASES = ["i am", "i'm", "my name", "i work", "my role", "my stack", "i joined"]
ROLE_WORDS = ["intern", "engineer", "developer", "backend", "frontend", "devops", "fullstack", "ml", "junior", "senior"]
# Reporting a change to a task ("I finished BI-01", "BI-03 is blocked").
STATUS_CHANGE_WORDS = ["complete", "completed", "done", "finished", "finish", "started", "working on",
                       "in progress", "blocked", "stuck", "skip", "skipped"]
# Explicit requests to change a task, even when phrased as a question ("can you mark BI-02 done?",
# "set BI-03 to in progress"). Requires a target status so "how do I set up the repo?" isn't one.
CHANGE_REQUEST_PATTERN = (
    r"\bmark\b|\b(set|move|update|change)\b[^?.!]*\b(to|as)\s+"
    r"(complete|completed|done|in progress|blocked|skipped|started|not started)"
)
# Asking about checklist state rather than about how to do something.
TRACKING_PHRASES = ["checklist", "progress", "my tasks", "next task", "remaining task", "what's left", "status of"]


def _is_question(text: str) -> bool:
    return "?" in text or text.startswith(QUESTION_STARTS)


def _classify_intent_with_llm(text: str) -> str:
    """Fallback intent classifier using LLM when keyword matching is inconclusive."""
    try:
        from app.agent.llm_loader import get_llm, is_mock_llm
        from langchain_core.messages import SystemMessage, HumanMessage

        if is_mock_llm():
            # In mock fallback, infer from common helper phrases
            lower = text.lower()
            if any(w in lower for w in ["help", "guide", "tell", "explain", "how", "what", "find"]):
                return "question"
            if any(w in lower for w in ["engineer", "developer", "stack", "work on"]):
                return "intro"
            return "other"

        llm = get_llm()
        system = SystemMessage(
            content=(
                "You are an intent classifier for a software engineering onboarding assistant.\n"
                "Classify the user message into exactly ONE of the following categories:\n"
                "- greeting (e.g. hello, good morning)\n"
                "- intro (e.g. I am a backend intern working on Python, my stack is React)\n"
                "- question (e.g. can you help me get set up, what is our PR review policy)\n"
                "- checklist_action (e.g. mark DEV-01 complete, task is blocked)\n"
                "- complete (e.g. finish onboarding, I am done with everything)\n"
                "- other (any other input)\n\n"
                "Respond ONLY with the category keyword."
            )
        )
        resp = llm.invoke([system, HumanMessage(content=text)])
        res_text = str(resp.content).strip().lower()
        for cat in ["greeting", "intro", "question", "checklist_action", "complete", "other"]:
            if cat in res_text:
                return cat
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"LLM intent classification fallback error: {e}")
    return "other"


def run(state: dict) -> dict:
    raw_text = _last_human_message(state)
    text = raw_text.lower()
    phase = state.get("phase", "greeting")

    # Dedicated first-impression path for demo UX.
    # If phase is greeting but the user's message already contains an intro, fast-track to collect_info.
    is_question = _is_question(text)
    if phase == "greeting":
        self_intro = any(k in text for k in SELF_INTRO_PHRASES)
        if self_intro or (not is_question and any(k in text for k in ROLE_WORDS)):
            return {"intent": "intro", "phase": "collect_info"}
        if is_question:
            # Answer from the knowledge base now; the intro can still happen on a later turn.
            return {"intent": "question", "phase": "greeting"}
        return {"intent": "greeting", "phase": "greeting"}

    mentions_task = bool(re.search(TASK_ID_PATTERN, text, flags=re.IGNORECASE)) or "task" in text
    reports_status = any(k in text for k in STATUS_CHANGE_WORDS)
    requests_change = mentions_task and bool(re.search(CHANGE_REQUEST_PATTERN, text))
    asks_tracking = any(k in text for k in TRACKING_PHRASES)

    intent = "other"
    if any(k in text for k in ["complete onboarding", "finish onboarding", "finalize onboarding"]):
        intent = "complete"
    elif asks_tracking or requests_change or (reports_status and not is_question):
        intent = "checklist_action"
    elif mentions_task and is_question:
        # e.g. "Where do I find the repository URL for BI-02?" needs documentation, not a status update.
        intent = "question"
    elif phase in ["greeting", "collect_info"] and any(
        k in text for k in ["hi", "hello", "hey", "i am", "my role", "intern", "junior", "senior", "backend", "frontend", "devops"]
    ):
        intent = "intro"
    elif "?" in text or any(k in text for k in ["how", "what", "where", "why", "policy", "architecture", "setup"]):
        intent = "question"

    # LLM fallback for ambiguous / natural queries
    if intent == "other" and raw_text:
        intent = _classify_intent_with_llm(raw_text)

    next_phase = phase
    if intent == "complete":
        next_phase = "completed"
    elif phase == "collect_info" and text:
        detected = identify_persona(text)
        if detected and detected.persona_key != FALLBACK_PERSONA.persona_key:
            next_phase = "first_task"
    elif state.get("onboarding_complete"):
        next_phase = "completed"

    return {
        "intent": intent,
        "detected_intent": intent,
        "phase": next_phase,
        "current_phase": next_phase,
    }


def detect_phase_transition(previous_state: dict, graph_result: dict) -> str:
    """Resolve phase transitions from graph output, defaulting to previous phase."""
    if graph_result.get("phase"):
        return graph_result["phase"]
    return previous_state.get("phase", "collect_info")
