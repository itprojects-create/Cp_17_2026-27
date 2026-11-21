"""
LangGraph supervisor workflow for stateful, autonomous developer onboarding.

Orchestrates:
1. Session State Rehydration (session_loader)
2. Intent & Context Understanding (router)
3. Persona Identification & Plan Generation (persona)
4. Knowledge Retrieval (rag)
5. Task Execution, Evidence Verification & Progress Tracking (checklist)
6. Starter Ticket Assignment (ticket)
7. HR Notification & Finalization (email)
8. Natural Response Synthesis (composer)
"""
import logging
from langgraph.graph import StateGraph, END
from app.agent.state import AgentState
from app.agent.nodes import (
    session_loader_run,
    router_run,
    persona_run,
    rag_run,
    checklist_run,
    ticket_run,
    email_run,
    composer_run,
)
from app.agent.nodes.verify import run as verify_run

logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    """Build and compile the supervisor onboarding agent graph."""
    builder = StateGraph(AgentState)

    # Core Graph Nodes
    builder.add_node("session_loader", session_loader_run)
    builder.add_node("router", router_run)
    builder.add_node("persona", persona_run)
    builder.add_node("rag", rag_run)
    builder.add_node("checklist", checklist_run)
    builder.add_node("ticket", ticket_run)
    builder.add_node("email", email_run)
    builder.add_node("composer", composer_run)
    builder.add_node("verify", verify_run)

    # 1. Entry point -> Rehydrate session state from database
    builder.set_entry_point("session_loader")
    builder.add_edge("session_loader", "router")

    # 2. Supervisor Routing from Router
    def _route_from_router(s: dict) -> str:
        intent = s.get("intent", "other")
        phase = s.get("phase", "greeting")
        onboarding_complete = s.get("onboarding_complete", False)

        logger.debug(
            "[Supervisor Edge: router -> ?] intent='%s', phase='%s', complete=%s",
            intent,
            phase,
            onboarding_complete,
        )

        # If already fully completed and not requesting a specific task action, let composer answer directly
        if onboarding_complete and intent not in ("checklist_action", "complete"):
            return "rag" if intent == "question" else "composer"

        if intent == "question":
            return "rag"
        if intent in ("greeting", "intro") or phase in ("greeting", "collect_info"):
            return "persona"
        elif intent == "checklist_action":
            return "checklist"
        elif intent == "complete":
            return "email"
        elif intent == "question":
            return "rag"
        else:
            return "rag"

    builder.add_conditional_edges(
        "router",
        _route_from_router,
        {
            "persona": "persona",
            "rag": "rag",
            "checklist": "checklist",
            "email": "email",
            "composer": "composer",
        },
    )

    # 3. Routing from Persona, RAG
    builder.add_edge("persona", "composer")
    builder.add_edge("rag", "composer")

    # 4. Supervisor Routing from Checklist
    def _route_after_checklist(s: dict) -> str:
        total = s.get("total_count", 0)
        completed = s.get("completed_count", 0)
        intent = s.get("intent")

        # Always verify the persisted mutation before allowing finalization.
        if (total > 0 and completed == total) or intent == "complete":
            logger.info("[Supervisor] Checking persisted completion state (%d/%d).", completed, total)
        return "verify"

    builder.add_conditional_edges(
        "checklist",
        _route_after_checklist,
        {
            "email": "email",
            "verify": "verify",
        },
    )

    def _route_after_verify(s: dict) -> str:
        result = s.get("verification_result") or {}
        if result.get("verified") is False:
            return "composer"
        total = s.get("total_count", 0)
        completed = s.get("completed_count", 0)
        return "email" if total > 0 and completed == total else "composer"

    builder.add_conditional_edges(
        "verify",
        _route_after_verify,
        {"email": "email", "composer": "composer"},
    )

    # 5. Routing from Email
    builder.add_edge("email", "composer")

    # 6. Post-Composer Routing (Optional Starter Ticket Trigger)
    def _route_composer(s: dict) -> str:
        phase = s.get("phase")
        ticket_assigned = s.get("ticket_assigned", False)
        if phase == "first_task" and not ticket_assigned:
            return "ticket"
        return "end"

    builder.add_conditional_edges(
        "composer",
        _route_composer,
        {
            "ticket": "ticket",
            "end": END,
        },
    )
    builder.add_edge("ticket", END)

    return builder.compile()


# Singleton compiled supervisor graph instance
graph = build_graph()


def invoke_agent(state: dict) -> dict:
    """
    Invoke the supervisor agent graph with the given state.
    Returns the final state after all tool calls, supervisor evaluations, and synthesized responses.
    """
    try:
        result = graph.invoke(state)
        return result
    except Exception as e:
        logger.error("Agent graph execution error: %s", e, exc_info=True)
        from langchain_core.messages import AIMessage
        fallback_msg = AIMessage(
            content="I encountered an issue processing your request. "
                    "Please try again, or ask me something else. "
                    "You can also check your checklist or browse the knowledge base directly."
        )
        state["messages"] = state.get("messages", []) + [fallback_msg]
        return state
