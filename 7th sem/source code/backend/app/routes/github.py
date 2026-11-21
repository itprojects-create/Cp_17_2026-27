"""
Real GitHub OAuth Integration Routes
-------------------------------------
Provides:
  GET  /api/github/oauth/redirect   → Return GitHub OAuth consent URL
  POST /api/github/oauth/callback   → Exchange code for token, save connection
  GET  /api/github/status           → Get current GitHub connection status
  GET  /api/github/data             → Fetch real repos / issues / PRs
  POST /api/github/disconnect       → Disconnect GitHub for user
"""

import httpx
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.utils import get_current_user
from app.config import settings
from app.db.database import get_db
from app.db.models import UserDB, UserIntegrationDB
from app.integrations.manager import integration_manager
from app.routes.dashboard import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/github", tags=["github"])


# ---------------------------------------------------------------------------
# Helper: persist / update GitHub row in user_integrations
# ---------------------------------------------------------------------------

def _upsert_github_row(
    db: Session,
    user_id: int,
    status: str,
) -> UserIntegrationDB:
    row = (
        db.query(UserIntegrationDB)
        .filter(
            UserIntegrationDB.user_id == user_id,
            UserIntegrationDB.integration == "github",
        )
        .first()
    )
    now = datetime.now(timezone.utc)
    if not row:
        row = UserIntegrationDB(
            user_id=user_id,
            integration="github",
            status=status,
            last_sync=now,
        )
        db.add(row)
    else:
        row.status = status
        row.last_sync = now

    db.commit()
    return row


def _get_user_github_token(db: Session, user_id: int) -> str | None:
    """
    Return the GitHub token for this user. Currently falls back to the global
    settings token (set after OAuth callback). Add a token column to
    UserIntegrationDB to store per-user tokens persistently.
    """
    row = (
        db.query(UserIntegrationDB)
        .filter(
            UserIntegrationDB.user_id == user_id,
            UserIntegrationDB.integration == "github",
        )
        .first()
    )
    if row and row.status == "connected":
        return getattr(settings, "GITHUB_TOKEN", None) or None
    return None


# ---------------------------------------------------------------------------
# 1. OAuth Redirect — return the GitHub consent URL to the frontend
# ---------------------------------------------------------------------------

@router.get("/oauth/redirect")
async def github_oauth_redirect(
    current_user: UserDB = Depends(get_current_user),
):
    client_id = getattr(settings, "GITHUB_CLIENT_ID", "").strip()
    if not client_id:
        raise HTTPException(
            status_code=503,
            detail=(
                "GitHub OAuth is not configured. "
                "Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET in your .env. "
                "Create an OAuth App at: https://github.com/settings/applications/new"
            ),
        )

    callback_url = getattr(settings, "GITHUB_OAUTH_CALLBACK_URL", "").strip()
    if not callback_url:
        callback_url = f"{settings.FRONTEND_BASE_URL}/integrations/github/callback"

    scopes = getattr(settings, "GITHUB_OAUTH_SCOPES", "read:user,repo,read:org").strip()
    state = f"user_{current_user.id}"

    params = {
        "client_id": client_id,
        "redirect_uri": callback_url,
        "scope": scopes,
        "state": state,
    }
    auth_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    return {"auth_url": auth_url}


# ---------------------------------------------------------------------------
# 2. OAuth Callback — frontend POSTs the code, we exchange it for a token
# ---------------------------------------------------------------------------

@router.post("/oauth/callback")
async def github_oauth_callback(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    code = payload.get("code", "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="Missing `code` from GitHub OAuth redirect.")

    client_id = getattr(settings, "GITHUB_CLIENT_ID", "").strip()
    client_secret = getattr(settings, "GITHUB_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=503,
            detail="GitHub OAuth credentials (GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET) not configured.",
        )

    # Exchange code for access token
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://github.com/login/oauth/access_token",
                json={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                },
                headers={"Accept": "application/json"},
            )
            token_data = resp.json()
    except Exception as exc:
        logger.error("GitHub token exchange failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"GitHub token exchange failed: {exc}")

    access_token = token_data.get("access_token", "")
    if not access_token:
        error = token_data.get("error_description") or token_data.get("error") or "Unknown OAuth error"
        raise HTTPException(status_code=400, detail=f"GitHub OAuth failed: {error}")

    # Verify the token by fetching the authenticated GitHub user
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            gh_resp = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"token {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            if gh_resp.status_code != 200:
                raise HTTPException(status_code=400, detail="GitHub returned an invalid token.")
            gh_user = gh_resp.json()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("GitHub user fetch failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Could not verify GitHub token: {exc}")

    github_username = gh_user.get("login", "")
    github_name = gh_user.get("name", "")
    github_avatar = gh_user.get("avatar_url", "")

    # Persist status in DB; store token in runtime settings for this process
    row = _upsert_github_row(db, current_user.id, "connected")
    settings.GITHUB_TOKEN = access_token  # type: ignore[attr-defined]
    settings.GITHUB_MODE = "real"  # type: ignore[attr-defined]

    now_iso = row.last_sync.isoformat() if row.last_sync else datetime.now(timezone.utc).isoformat()

    await ws_manager.broadcast({
        "type": "integration_status",
        "integration_id": "github",
        "status": "connected",
        "lastSync": now_iso,
    })

    return {
        "ok": True,
        "status": "connected",
        "github_username": github_username,
        "github_name": github_name,
        "github_avatar": github_avatar,
        "lastSync": now_iso,
    }


# ---------------------------------------------------------------------------
# 3. Status
# ---------------------------------------------------------------------------

@router.get("/status")
async def github_status(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    row = (
        db.query(UserIntegrationDB)
        .filter(
            UserIntegrationDB.user_id == current_user.id,
            UserIntegrationDB.integration == "github",
        )
        .first()
    )
    if not row or row.status != "connected":
        return {"connected": False, "status": row.status if row else "disconnected"}

    integration = integration_manager.integrations["github"]
    if not await integration.verify():
        row.status = "unavailable"
        db.commit()
        return {
            "connected": False,
            "status": "unavailable",
            "lastSync": row.last_sync.isoformat() if row.last_sync else None,
        }

    return {
        "connected": True,
        "status": "connected",
        "lastSync": row.last_sync.isoformat() if row.last_sync else None,
    }


# ---------------------------------------------------------------------------
# 4. Real GitHub Data
# ---------------------------------------------------------------------------

@router.get("/data")
async def get_github_data(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """
    Return real GitHub data for the connected user:
    - Authenticated user profile
    - 10 most recently updated repos
    - 10 open issues assigned to user
    - 10 open PRs authored by user
    """
    token = _get_user_github_token(db, current_user.id)
    if not token or "your-github-token" in token:
        raise HTTPException(
            status_code=403,
            detail="GitHub is not connected. Connect your GitHub account first.",
        )

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    result: dict = {}

    async with httpx.AsyncClient(timeout=15.0) as client:
        # User profile
        try:
            r = await client.get("https://api.github.com/user", headers=headers)
            if r.status_code == 200:
                u = r.json()
                result["user"] = {
                    "login": u.get("login"),
                    "name": u.get("name"),
                    "avatar_url": u.get("avatar_url"),
                    "html_url": u.get("html_url"),
                    "public_repos": u.get("public_repos", 0),
                    "followers": u.get("followers", 0),
                    "following": u.get("following", 0),
                    "bio": u.get("bio"),
                }
            else:
                result["user"] = None
        except Exception as exc:
            logger.warning("GitHub user fetch: %s", exc)
            result["user"] = None

        # Repos
        try:
            r = await client.get(
                "https://api.github.com/user/repos",
                headers=headers,
                params={"sort": "updated", "per_page": 10, "type": "owner"},
            )
            if r.status_code == 200:
                result["repos"] = [
                    {
                        "id": repo["id"],
                        "name": repo["name"],
                        "full_name": repo["full_name"],
                        "description": repo.get("description"),
                        "html_url": repo["html_url"],
                        "language": repo.get("language"),
                        "stargazers_count": repo.get("stargazers_count", 0),
                        "forks_count": repo.get("forks_count", 0),
                        "open_issues_count": repo.get("open_issues_count", 0),
                        "updated_at": repo.get("updated_at"),
                        "private": repo.get("private", False),
                        "visibility": repo.get("visibility", "public"),
                    }
                    for repo in r.json()
                ]
            else:
                result["repos"] = []
        except Exception as exc:
            logger.warning("GitHub repos fetch: %s", exc)
            result["repos"] = []

        # Issues assigned to user
        try:
            r = await client.get(
                "https://api.github.com/issues",
                headers=headers,
                params={"state": "open", "filter": "assigned", "per_page": 10},
            )
            if r.status_code == 200:
                result["issues"] = [
                    {
                        "id": iss["id"],
                        "number": iss["number"],
                        "title": iss["title"],
                        "html_url": iss["html_url"],
                        "state": iss["state"],
                        "created_at": iss.get("created_at"),
                        "updated_at": iss.get("updated_at"),
                        "repo": (iss.get("repository") or {}).get("full_name", ""),
                        "labels": [lb["name"] for lb in iss.get("labels", [])],
                        "comments": iss.get("comments", 0),
                    }
                    for iss in r.json()
                ]
            else:
                result["issues"] = []
        except Exception as exc:
            logger.warning("GitHub issues fetch: %s", exc)
            result["issues"] = []

        # Open PRs authored by user
        login = (result.get("user") or {}).get("login", "")
        try:
            if login:
                r = await client.get(
                    "https://api.github.com/search/issues",
                    headers=headers,
                    params={
                        "q": f"is:pr is:open author:{login}",
                        "sort": "updated",
                        "per_page": 10,
                    },
                )
                if r.status_code == 200:
                    items = r.json().get("items", [])
                    result["pull_requests"] = [
                        {
                            "id": pr["id"],
                            "number": pr["number"],
                            "title": pr["title"],
                            "html_url": pr["html_url"],
                            "state": pr["state"],
                            "created_at": pr.get("created_at"),
                            "updated_at": pr.get("updated_at"),
                            "repo": "/".join(pr.get("repository_url", "").split("/")[-2:]),
                            "labels": [lb["name"] for lb in pr.get("labels", [])],
                        }
                        for pr in items
                    ]
                else:
                    result["pull_requests"] = []
            else:
                result["pull_requests"] = []
        except Exception as exc:
            logger.warning("GitHub PRs fetch: %s", exc)
            result["pull_requests"] = []

    return result


# ---------------------------------------------------------------------------
# 5. Disconnect
# ---------------------------------------------------------------------------

@router.post("/disconnect")
async def github_disconnect(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    row = (
        db.query(UserIntegrationDB)
        .filter(
            UserIntegrationDB.user_id == current_user.id,
            UserIntegrationDB.integration == "github",
        )
        .first()
    )
    if row:
        row.status = "disconnected"
        row.last_sync = datetime.now(timezone.utc)
        db.commit()

    # Clear runtime token
    settings.GITHUB_TOKEN = ""  # type: ignore[attr-defined]
    settings.GITHUB_MODE = "mock"  # type: ignore[attr-defined]

    await ws_manager.broadcast({
        "type": "integration_status",
        "integration_id": "github",
        "status": "disconnected",
        "lastSync": datetime.now(timezone.utc).isoformat(),
    })

    return {"ok": True, "status": "disconnected"}
