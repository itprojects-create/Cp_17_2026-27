import httpx
import logging
from typing import Any, Dict

from app.integrations.base import IntegrationBase
from app.config import settings
from app.models.integration_schemas import (
    GitHubCreateIssueInput,
    GitHubCreateIssueOutput,
    GitHubVerifyRepoAccessInput,
    GitHubVerifyRepoAccessOutput,
    GitHubInviteInput,
    GitHubGrantAccessInput,
)

logger = logging.getLogger(__name__)


class GitHubIntegration(IntegrationBase):
    """
    Handles GitHub repository access, starter issues, and org invitations.
    Supports 'mock' mode for local development and 'real' mode via GitHub REST API.
    """

    def __init__(self):
        pass

    @property
    def mode(self) -> str:
        return getattr(settings, "GITHUB_MODE", "mock").lower().strip()

    @property
    def token(self) -> str:
        return getattr(settings, "GITHUB_TOKEN", "")

    async def verify(self) -> bool:
        """Verify GitHub credentials."""
        if self.mode == "mock":
            return True

        if not self.token or "your-github-token" in self.token:
            logger.error("GitHub verification failed: missing or placeholder GITHUB_TOKEN.")
            return False

        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    "https://api.github.com/user",
                    headers={
                        "Authorization": f"token {self.token}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                    timeout=10.0,
                )
                return res.status_code in (200, 204)
        except Exception as e:
            logger.error(f"GitHub verification failed: {e}")
            return False


    async def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Route to the appropriate action method."""
        if action in ("create_ticket", "create_issue", "create_starter_issue"):
            return await self.create_issue(params)
        elif action in ("verify_repo_access", "verify_access"):
            return await self.verify_repo_access(params)
        elif action == "invite_to_org":
            return await self.invite_to_org(params)
        elif action == "add_to_team":
            return await self.invite_to_org(params)
        elif action == "grant_repo_access":
            return await self.grant_repo_access(params)
        else:
            raise ValueError(f"Unknown GitHub action: {action}")

    async def create_issue(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a starter issue/task on GitHub with structured validation and output."""
        # Support fallback parameter names
        normalized_params = {
            "title": params.get("title") or params.get("summary") or "Starter Onboarding Task",
            "description": params.get("description") or params.get("body") or "First assigned onboarding task",
            "repo_name": params.get("repo_name", "backend-starter"),
            "org_name": params.get("org_name", "NovaByte-AI"),
        }

        try:
            validated = GitHubCreateIssueInput(**normalized_params)
        except Exception as exc:
            return GitHubCreateIssueOutput(
                status="error",
                ticket_id="GH-INVALID",
                mode=self.mode,
                error=f"Invalid GitHub input parameters: {exc}",
            ).model_dump()

        ticket_id = f"GH-{validated.repo_name}-101"
        url = f"https://github.com/{validated.org_name}/{validated.repo_name}/issues/101"

        if self.mode == "mock":
            logger.info(f"[MOCK GITHUB] Created issue {ticket_id}: {validated.title}")
            return GitHubCreateIssueOutput(
                status="success",
                ticket_id=ticket_id,
                url=url,
                mode="mock",
            ).model_dump()

        # Real Mode
        if not await self.verify():
            return GitHubCreateIssueOutput(
                status="error",
                ticket_id="GH-AUTH-FAIL",
                mode="real",
                error="GitHub configuration missing: GITHUB_TOKEN is required for real mode.",
            ).model_dump()

        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    f"https://api.github.com/repos/{validated.org_name}/{validated.repo_name}/issues",
                    headers={
                        "Authorization": f"token {self.token}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                    json={"title": validated.title, "body": validated.description},
                    timeout=15.0,
                )
                if res.status_code in (200, 201):
                    data = res.json()
                    return GitHubCreateIssueOutput(
                        status="success",
                        ticket_id=f"GH-#{data.get('number', 101)}",
                        url=data.get("html_url", url),
                        mode="real",
                    ).model_dump()
                return GitHubCreateIssueOutput(
                    status="error",
                    ticket_id="GH-ERROR",
                    mode="real",
                    error=f"GitHub API error ({res.status_code}): {res.text}",
                ).model_dump()
        except Exception as e:
            logger.error(f"GitHub create_issue failed: {e}")
            return GitHubCreateIssueOutput(
                status="error",
                ticket_id="GH-ERROR",
                mode="real",
                error=f"GitHub request exception: {str(e)}",
            ).model_dump()

    async def verify_repo_access(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Verify repository access for a user or bot token."""
        try:
            validated = GitHubVerifyRepoAccessInput(**params)
        except Exception as exc:
            return GitHubVerifyRepoAccessOutput(
                status="error",
                accessible=False,
                repo_name=params.get("repo_name", "unknown"),
                mode=self.mode,
                error=f"Invalid repository verification parameters: {exc}",
            ).model_dump()

        if self.mode == "mock":
            logger.info(f"[MOCK GITHUB] Verified access for repo {validated.repo_name}")
            return GitHubVerifyRepoAccessOutput(
                status="success",
                accessible=True,
                repo_name=validated.repo_name,
                mode="mock",
            ).model_dump()

        if not await self.verify():
            return GitHubVerifyRepoAccessOutput(
                status="error",
                accessible=False,
                repo_name=validated.repo_name,
                mode="real",
                error="GitHub token not configured or invalid.",
            ).model_dump()

        try:
            async with httpx.AsyncClient() as client:
                if validated.github_handle:
                    res = await client.get(
                        f"https://api.github.com/repos/{validated.org_name}/{validated.repo_name}/collaborators/{validated.github_handle}",
                        headers={
                            "Authorization": f"token {self.token}",
                            "Accept": "application/vnd.github.v3+json",
                        },
                        timeout=10.0,
                    )
                else:
                    res = await client.get(
                        f"https://api.github.com/repos/{validated.org_name}/{validated.repo_name}",
                        headers={
                            "Authorization": f"token {self.token}",
                            "Accept": "application/vnd.github.v3+json",
                        },
                        timeout=10.0,
                    )
                accessible = res.status_code in (200, 204)
                return GitHubVerifyRepoAccessOutput(
                    status="success" if accessible else "error",
                    accessible=accessible,
                    repo_name=validated.repo_name,
                    mode="real",
                    error=None if accessible else f"GitHub returned status code {res.status_code}",
                ).model_dump()
        except Exception as e:
            logger.error(f"GitHub verify_repo_access failed: {e}")
            return GitHubVerifyRepoAccessOutput(
                status="error",
                accessible=False,
                repo_name=validated.repo_name,
                mode="real",
                error=str(e),
            ).model_dump()

    async def invite_to_org(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Invite user to the GitHub organization."""
        try:
            validated = GitHubInviteInput(**params)
        except Exception as exc:
            return {"status": "error", "mode": self.mode, "error": str(exc)}

        if self.mode == "mock":
            logger.info(f"[MOCK GITHUB] Invited {validated.github_handle} to organization {validated.org_name}")
            return {"status": "success", "mode": "mock", "handle": validated.github_handle}

        if not await self.verify():
            return {"status": "error", "mode": "real", "error": "GitHub credentials not configured."}

        try:
            async with httpx.AsyncClient() as client:
                res = await client.put(
                    f"https://api.github.com/orgs/{validated.org_name}/memberships/{validated.github_handle}",
                    headers={
                        "Authorization": f"token {self.token}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                    timeout=15.0,
                )
                if res.status_code in [200, 201]:
                    return {"status": "success", "mode": "real", "handle": validated.github_handle}
                else:
                    return {"status": "error", "mode": "real", "message": res.text, "error": res.text}
        except Exception as e:
            logger.error(f"GitHub invite_to_org failed: {e}")
            return {"status": "error", "mode": "real", "error": str(e), "message": str(e)}

    async def grant_repo_access(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Grant repository access to a user."""
        try:
            validated = GitHubGrantAccessInput(**params)
        except Exception as exc:
            return {"status": "error", "mode": self.mode, "error": str(exc)}

        if self.mode == "mock":
            logger.info(f"[MOCK GITHUB] Granted {validated.permission} access to {validated.repo_name} for {validated.github_handle}")
            return {"status": "success", "mode": "mock", "repo": validated.repo_name}

        if not await self.verify():
            return {"status": "error", "mode": "real", "error": "GitHub credentials not configured."}

        try:
            async with httpx.AsyncClient() as client:
                res = await client.put(
                    f"https://api.github.com/repos/{validated.org_name}/{validated.repo_name}/collaborators/{validated.github_handle}",
                    headers={
                        "Authorization": f"token {self.token}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                    json={"permission": validated.permission},
                    timeout=15.0,
                )
                if res.status_code in [201, 204]:
                    return {"status": "success", "mode": "real", "repo": validated.repo_name}
                else:
                    return {"status": "error", "mode": "real", "message": res.text, "error": res.text}
        except Exception as e:
            logger.error(f"GitHub grant_repo_access failed: {e}")
            return {"status": "error", "mode": "real", "error": str(e), "message": str(e)}
