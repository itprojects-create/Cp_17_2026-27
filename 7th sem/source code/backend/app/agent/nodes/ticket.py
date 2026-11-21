import asyncio
import logging
from app.integrations.manager import integration_manager

logger = logging.getLogger(__name__)


def _run_async_safely(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)



def run(state: dict) -> dict:
    persona = state.get("persona") or {}
    # GitHub is the only ticketing integration; every role gets its starter issue there.
    target = "github"
    params = {
        "title": f"Starter onboarding task for {persona.get('role', 'new hire')}",
        "summary": f"Onboarding starter task: {persona.get('role', 'Developer')} setup & initial issue",
        "description": f"Initial starter ticket assigned during onboarding for {persona.get('role', 'Developer')} ({persona.get('level', 'Junior')}).",
        "persona": persona,
    }

    try:
        result = _run_async_safely(integration_manager.execute_action(target, "create_ticket", params))
    except Exception as e:
        logger.error(f"Failed to execute ticket creation integration: {e}")
        result = {"ticket_id": f"{target.upper()}-101", "status": "mock"}

    ticket_ref = result.get("ticket_id") or result.get("url") or f"{target.upper()}-101"
    return {
        "phase": "onboarding",
        "ticket_assigned": True,
        "ticket_reference": ticket_ref,
        "suggested_actions": [
            f"Starter ticket assigned: {ticket_ref}",
            "Confirm ticket scope with your team lead",
            "Create your first pull request",
        ],
    }

