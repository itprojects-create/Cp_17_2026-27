import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables: checks backend/.env first, then root .env
load_dotenv(BASE_DIR / ".env")
load_dotenv()


def normalize_smtp_password(password: str, host: str) -> str:
    """Gmail shows app passwords in groups ("abcd efgh ijkl mnop"); the spaces are not part of it."""
    password = (password or "").strip()
    if "gmail" in (host or "").lower() or "googlemail" in (host or "").lower():
        password = password.replace(" ", "")
    return password


def strip_bearer_prefix(key: str) -> str:
    """Accept API keys pasted with the "Bearer " prefix from providers' curl samples.

    HTTP clients add that prefix themselves, so leaving it in sends it twice and the
    provider rejects the key.
    """
    return re.sub(r"^Bearer\s+", "", (key or "").strip(), flags=re.IGNORECASE)


class Settings:
    """Centralized, production-safe application settings."""

    # --- Paths ---
    BASE_DIR: Path = BASE_DIR
    KNOWLEDGE_BASE_DIR: Path = BASE_DIR / "knowledge_base"
    AGENT_DATA_DIR: Path = BASE_DIR / "agent_data"
    TEMPLATES_DIR: Path = BASE_DIR / "templates"
    CHROMA_DB_DIR: Path = BASE_DIR / "chroma_db"
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", str(BASE_DIR / "onboarding.db"))

    # --- LLM Providers ---
    # Primary provider, plus a fallback that takes over any call the primary fails.
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "nvidia").lower().strip()
    LLM_FALLBACK_PROVIDER: str = os.getenv("LLM_FALLBACK_PROVIDER", "gemini").lower().strip()
    LLM_PRIMARY_TIMEOUT: float = float(os.getenv("LLM_PRIMARY_TIMEOUT", "60"))

    # Tolerate keys pasted together with the "Bearer " prefix from NVIDIA's curl samples;
    # the client adds that prefix itself, so it would otherwise be sent twice and rejected.
    NVIDIA_API_KEY: str = strip_bearer_prefix(os.getenv("NVIDIA_API_KEY", ""))
    NVIDIA_MODEL: str = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b").strip()
    NVIDIA_BASE_URL: str = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").strip()
    NVIDIA_ENABLE_THINKING: bool = os.getenv("NVIDIA_ENABLE_THINKING", "false").lower() == "true"

    GEMINI_API_KEY: str = (os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")).strip()
    GOOGLE_API_KEY: str = (os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")).strip()
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip()

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "").strip()
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small").strip()

    GROK_API_KEY: str = os.getenv("GROK_API_KEY", "").strip()
    GROK_MODEL: str = os.getenv("GROK_MODEL", "grok-3-latest").strip()
    GROK_BASE_URL: str = os.getenv("GROK_BASE_URL", "https://api.x.ai/v1").strip()

    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "").strip()
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest").strip()
    MOCK_LLM_ENABLED: bool = os.getenv("MOCK_LLM_ENABLED", "false").lower() == "true"

    # --- Security & Authentication ---
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-this").strip()
    PASSWORD_RESET_EXPIRE_MINUTES: int = int(os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "30"))
    # Invite links give new employees time to act on the email, unlike a short-lived reset.
    INVITE_EXPIRE_HOURS: int = int(os.getenv("INVITE_EXPIRE_HOURS", "72"))
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "").strip()

    # --- Server & Networking ---
    HOST: str = os.getenv("HOST", "0.0.0.0").strip()
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    FRONTEND_BASE_URL: str = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173").strip()
    CORS_ORIGINS: List[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
        if origin.strip()
    ]

    # --- Email (SMTP) ---
    EMAIL_MODE: str = os.getenv("EMAIL_MODE", "mock").lower().strip()  # "mock" | "real"
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "").strip()
    SMTP_PASSWORD: str = normalize_smtp_password(
        os.getenv("SMTP_PASSWORD", ""), os.getenv("SMTP_HOST", "smtp.gmail.com")
    )
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "").strip() or os.getenv("SMTP_USER", "").strip() or "onboarding@novabyte.com"
    # Display name shown in recipients' inboxes ("NovaByte Onboarding <you@gmail.com>").
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "NovaByte Onboarding").strip()
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")
    SMTP_USE_SSL: bool = os.getenv("SMTP_USE_SSL", "false").lower() in ("true", "1", "yes")
    HR_EMAIL: str = os.getenv("HR_EMAIL", "hr@novabyte.com").strip()

    # --- Integrations ---
    GITHUB_MODE: str = os.getenv("GITHUB_MODE", "mock").lower().strip()  # "mock" | "real"
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "").strip()
    GITHUB_CLIENT_ID: str = os.getenv("GITHUB_CLIENT_ID", "").strip()
    GITHUB_CLIENT_SECRET: str = os.getenv("GITHUB_CLIENT_SECRET", "").strip()
    GITHUB_OAUTH_CALLBACK_URL: str = os.getenv("GITHUB_OAUTH_CALLBACK_URL", "").strip()
    GITHUB_OAUTH_SCOPES: str = os.getenv("GITHUB_OAUTH_SCOPES", "read:user,repo,read:org").strip()
    GITHUB_ORG: str = os.getenv("GITHUB_ORG", "NovaByte-AI").strip()
    GITHUB_REPO: str = os.getenv("GITHUB_REPO", "backend-starter").strip()

    # --- RAG & Vector Search ---
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "5"))
    RAG_SCORE_THRESHOLD: float = float(os.getenv("RAG_SCORE_THRESHOLD", "0.3"))

    def validate_configuration(self) -> Dict[str, Any]:
        """
        Validate application configuration on startup.
        - Enforces strict security checks in production (DEBUG=False).
        - Logs helpful status warnings without leaking sensitive credentials.
        - Gracefully handles missing optional integration credentials.
        """
        issues = []
        warnings = []

        # 1. JWT Secret validation
        insecure_defaults = {"change-this", "secret", "your-secret-key", "default-secret", ""}
        if not self.DEBUG and (not self.JWT_SECRET_KEY or self.JWT_SECRET_KEY in insecure_defaults):
            issues.append(
                "FATAL: Insecure or default JWT_SECRET_KEY configured in production mode. "
                "Please set a strong JWT_SECRET_KEY in your environment."
            )
        elif self.JWT_SECRET_KEY in insecure_defaults:
            warnings.append(
                "Notice: Using default development JWT_SECRET_KEY. "
                "Set a secure JWT_SECRET_KEY before deploying to production."
            )

        # 2. LLM Provider key validation
        provider = self.LLM_PROVIDER
        if provider == "nvidia":
            if not self.NVIDIA_API_KEY or self.NVIDIA_API_KEY.startswith("your-"):
                warnings.append(
                    "LLM provider is set to 'nvidia' but NVIDIA_API_KEY is missing or a placeholder. "
                    f"Requests will use the fallback provider '{self.LLM_FALLBACK_PROVIDER}' if it is configured."
                )
            elif "/" not in self.NVIDIA_MODEL or " " in self.NVIDIA_MODEL:
                warnings.append(
                    f"NVIDIA_MODEL '{self.NVIDIA_MODEL}' is not a model ID. Use the ID from the NVIDIA API catalog, "
                    "e.g. 'nvidia/nemotron-3.5-lightning-30b-a3b', not the display name."
                )
        elif provider in ("gemini", "google"):
            if not self.GEMINI_API_KEY or self.GEMINI_API_KEY.startswith("your-"):
                warnings.append(
                    "LLM provider is set to 'gemini' but GEMINI_API_KEY / GOOGLE_API_KEY is missing or a placeholder. "
                    "The agent will operate using the deterministic Mock LLM fallback."
                )
        elif provider == "openai":
            if not self.OPENAI_API_KEY or self.OPENAI_API_KEY.startswith("sk-your-"):
                warnings.append(
                    "LLM provider is set to 'openai' but OPENAI_API_KEY is missing or a placeholder. "
                    "The agent will operate using the deterministic Mock LLM fallback."
                )
        elif provider == "grok":
            if not self.GROK_API_KEY or self.GROK_API_KEY.startswith("your-"):
                warnings.append(
                    "LLM provider is set to 'grok' but GROK_API_KEY is missing. "
                    "The agent will operate using the deterministic Mock LLM fallback."
                )
        elif provider == "anthropic":
            if not self.ANTHROPIC_API_KEY or self.ANTHROPIC_API_KEY.startswith("your-"):
                warnings.append(
                    "LLM provider is set to 'anthropic' but ANTHROPIC_API_KEY is missing. "
                    "The agent will operate using the deterministic Mock LLM fallback."
                )

        # 3. Integration validations (Mock mode vs Real mode)
        if self.EMAIL_MODE == "real":
            if not self.SMTP_USER or not self.SMTP_PASSWORD:
                warnings.append(
                    "EMAIL_MODE is set to 'real' but SMTP_USER or SMTP_PASSWORD is not configured. "
                    "Live email sending may fail."
                )
        else:
            logger.info("Email integration is running in mock mode (files written to backend/sent_emails/).")

        if self.GITHUB_MODE == "real":
            if not self.GITHUB_TOKEN or "your-github-token" in self.GITHUB_TOKEN:
                warnings.append("GITHUB_MODE is 'real' but GITHUB_TOKEN is missing or a placeholder.")

        for warn in warnings:
            logger.warning("⚙️ Config Warning: %s", warn)

        if issues:
            for issue in issues:
                logger.critical("🛑 Config Error: %s", issue)
            raise RuntimeError("\n".join(issues))

        return {"status": "ok", "warnings_count": len(warnings)}

    def get_sanitized_summary(self) -> Dict[str, Any]:
        """Return safe configuration metadata with all secrets masked."""
        def _mask(val: str) -> str:
            if not val:
                return "<not set>"
            if len(val) <= 6:
                return "***"
            return f"{val[:3]}***{val[-3:]}"

        return {
            "debug": self.DEBUG,
            "host": self.HOST,
            "port": self.PORT,
            "frontend_base_url": self.FRONTEND_BASE_URL,
            "llm_provider": self.LLM_PROVIDER,
            "llm_fallback_provider": self.LLM_FALLBACK_PROVIDER,
            "nvidia_configured": bool(self.NVIDIA_API_KEY and not self.NVIDIA_API_KEY.startswith("your-")),
            "gemini_configured": bool(self.GEMINI_API_KEY and not self.GEMINI_API_KEY.startswith("your-")),
            "openai_configured": bool(self.OPENAI_API_KEY and not self.OPENAI_API_KEY.startswith("sk-your-")),
            "grok_configured": bool(self.GROK_API_KEY and not self.GROK_API_KEY.startswith("your-")),
            "anthropic_configured": bool(self.ANTHROPIC_API_KEY and not self.ANTHROPIC_API_KEY.startswith("your-")),
            "email_mode": self.EMAIL_MODE,
            "github_mode": self.GITHUB_MODE,
            "github_oauth_configured": bool(self.GITHUB_CLIENT_ID and self.GITHUB_CLIENT_SECRET),
            "jwt_secret_configured": bool(self.JWT_SECRET_KEY and self.JWT_SECRET_KEY != "change-this"),
            "google_client_id_configured": bool(self.GOOGLE_CLIENT_ID),
        }


settings = Settings()
