import asyncio
import logging
from typing import Any, Dict, List, Optional
from langchain_core.tools import tool

from app.integrations.manager import integration_manager
from app.models.integration_schemas import (
    GitHubCreateIssueInput,
    GitHubVerifyRepoAccessInput,
    EmailCompletionReportInput,
)

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Safely executes an async coroutine across sync and async contexts."""
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


@tool(args_schema=GitHubCreateIssueInput)
def github_create_starter_issue(
    title: str,
    description: str = "",
    repo_name: str = "backend-starter",
    org_name: str = "NovaByte-AI",
) -> Dict[str, Any]:
    """
    Create a starter issue/ticket on GitHub for the onboarding developer.
    Returns structured output with status, ticket_id, url, and mode.
    """
    try:
        payload = {
            "title": title,
            "description": description,
            "repo_name": repo_name,
            "org_name": org_name,
        }
        res = _run_async(integration_manager.execute_action("github", "create_issue", payload))
        return res
    except Exception as e:
        logger.error("github_create_starter_issue tool error: %s", e)
        return {
            "status": "error",
            "mode": "error",
            "error": str(e),
            "message": str(e),
        }


@tool(args_schema=GitHubVerifyRepoAccessInput)
def github_verify_repo_access(
    repo_name: str,
    github_handle: Optional[str] = None,
    org_name: str = "NovaByte-AI",
) -> Dict[str, Any]:
    """
    Verify repository access permissions on GitHub.
    Returns structured output with status, accessible boolean, repo_name, and mode.
    """
    try:
        payload = {
            "repo_name": repo_name,
            "github_handle": github_handle,
            "org_name": org_name,
        }
        res = _run_async(integration_manager.execute_action("github", "verify_repo_access", payload))
        return res
    except Exception as e:
        logger.error("github_verify_repo_access tool error: %s", e)
        return {
            "status": "error",
            "accessible": False,
            "repo_name": repo_name,
            "mode": "error",
            "error": str(e),
            "message": str(e),
        }


@tool(args_schema=EmailCompletionReportInput)
def email_send_completion_report(
    session_id: str,
    recipient: Optional[str] = None,
    name: Optional[str] = None,
    role: Optional[str] = None,
    team: Optional[str] = None,
    experience_level: Optional[str] = None,
    tech_stack: Optional[List[str]] = None,
    completed_items: Optional[List[Any]] = None,
    pending_items: Optional[List[Any]] = None,
    ticket: Optional[str] = None,
    confidence_score: Optional[float] = None,
    verification_info: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate and send the final HR onboarding completion email report.
    Returns structured output with status, recipient, mode, and file path.
    """
    try:
        payload = {
            "session_id": session_id,
            "recipient": recipient,
            "name": name,
            "role": role,
            "team": team,
            "experience_level": experience_level,
            "tech_stack": tech_stack or [],
            "completed_items": completed_items or [],
            "pending_items": pending_items or [],
            "ticket": ticket,
            "confidence_score": confidence_score,
            "verification_info": verification_info,
        }
        res = _run_async(integration_manager.execute_action("email", "send_completion_email", payload))
        return res
    except Exception as e:
        logger.error("email_send_completion_report tool error: %s", e)
        return {
            "status": "error",
            "recipient": recipient or "unknown",
            "mode": "error",
            "error": str(e),
            "message": str(e),
        }
