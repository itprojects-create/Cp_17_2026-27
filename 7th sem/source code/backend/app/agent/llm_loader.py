"""
LLM loader with a primary provider and a runtime fallback.

LLM_PROVIDER picks the primary (default: nvidia, serving nvidia/nemotron-3.5-lightning-30b-a3b
through NVIDIA's OpenAI-compatible API). LLM_FALLBACK_PROVIDER (default: gemini)
handles any call the primary fails. Supported providers: nvidia, gemini (alias:
google), openai, grok, anthropic. A deterministic mock LLM is used only when
MOCK_LLM_ENABLED=true and no real provider is configured.
"""
import os
from datetime import datetime, timezone
import logging
import re
import importlib
from typing import Optional
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.runnables import Runnable
from app.config import settings

logger = logging.getLogger(__name__)


class MockChatLLM(BaseChatModel):
    """Deterministic mock LLM for development without API keys."""

    model_name: str = "mock-llm"

    @property
    def _llm_type(self) -> str:
        return "mock-chat"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        from langchain_core.outputs import ChatResult, ChatGeneration

        last_human = ""
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "human":
                last_human = msg.content.lower()
                break
            elif hasattr(msg, "role") and msg.role == "user":
                last_human = msg.content.lower()
                break

        # Rule-based tool calls so fallback mode can still update/check checklist.
        task_match = re.search(r"\b([A-Z]{2,}(?:-[A-Z]{1,3})?-\d+|[A-Z]{2,}-\d+)\b", last_human.upper())
        if task_match:
            item_id = task_match.group(1)
            status = None
            if any(w in last_human for w in ["complete", "completed", "done", "finish", "finished"]):
                status = "Completed"
            elif any(w in last_human for w in ["start", "started", "in progress", "working"]):
                status = "In Progress"
            elif any(w in last_human for w in ["block", "blocked", "stuck"]):
                status = "Blocked"
            elif any(w in last_human for w in ["skip", "skipped"]):
                status = "Skipped"

            if status:
                args = {"item_id": item_id, "new_status": status}
                if status == "Completed":
                    args["completion_evidence"] = last_human
                    args["completion_source"] = "user_confirmation"
                ai_msg = AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "update_checklist_item",
                        "args": args,
                        "id": "mock-tool-update-checklist"
                    }]
                )
                return ChatResult(generations=[ChatGeneration(message=ai_msg)])

        if any(w in last_human for w in ["checklist", "my tasks", "tasks"]) and not any(w in last_human for w in ["complete", "completed", "done", "start", "blocked", "skip"]):
            ai_msg = AIMessage(
                content="",
                tool_calls=[{
                    "name": "get_checklist",
                    "args": {},
                    "id": "mock-tool-get-checklist"
                }]
            )
            return ChatResult(generations=[ChatGeneration(message=ai_msg)])

        if any(w in last_human for w in ["progress", "percentage", "how much", "status"]):
            ai_msg = AIMessage(
                content="",
                tool_calls=[{
                    "name": "get_progress",
                    "args": {},
                    "id": "mock-tool-get-progress"
                }]
            )
        # Check if there is retrieved context in system message
        system_text = ""
        for msg in messages:
            if hasattr(msg, "type") and msg.type == "system":
                system_text += str(msg.content)
            elif hasattr(msg, "role") and msg.role == "system":
                system_text += str(msg.content)

        if "\n\nContext:\n" in system_text:
            context_part = system_text.split("\n\nContext:\n", 1)[1]
            if "\n\nTool Results:" in context_part:
                context_part = context_part.split("\n\nTool Results:", 1)[0]
            if "\n\nSuggested next actions:" in context_part:
                context_part = context_part.split("\n\nSuggested next actions:", 1)[0]

            context_part = context_part.strip()
            if not context_part:
                content = (
                    "The knowledge base does not provide enough information to answer this question. "
                    "Please reach out to your team lead, HR, or IT for further assistance."
                )
            else:
                first_lines = [l for l in context_part.splitlines() if l.strip() and not l.strip().startswith("###") and not l.strip().startswith("- ") and not l.strip().startswith("Sources:")]
                summary = " ".join(first_lines[:3]) if first_lines else context_part[:250]
                content = f"Based on our documentation:\n\n{summary}"
            ai_msg = AIMessage(content=content)
            return ChatResult(generations=[ChatGeneration(message=ai_msg)])

        if "Intent: question" in system_text and "\n\nContext:\n" not in system_text:
            content = (
                "The knowledge base does not provide enough information to answer this question. "
                "Please reach out to your team lead, HR, or IT for further assistance."
            )
            ai_msg = AIMessage(content=content)
            return ChatResult(generations=[ChatGeneration(message=ai_msg)])

        # Context-aware mock responses
        if any(w in last_human for w in ["hi", "hello", "hey", "start"]):
            content = (
                "Welcome to NovaByte! 🚀 I'm your AI onboarding assistant.\n\n"
                "I'll guide you through your entire onboarding journey. To get started, "
                "could you tell me:\n"
                "1. **Your name** and **role** (e.g., Backend, Frontend, DevOps, ML)\n"
                "2. **Experience level** (Intern, Junior, Senior)\n"
                "3. **Tech stack** you're familiar with\n\n"
                "This helps me personalize your onboarding experience!"
            )
        elif any(w in last_human for w in ["backend", "frontend", "devops", "ml", "fullstack"]):
            content = (
                "Great! I've identified your profile. Let me set up your personalized "
                "onboarding checklist.\n\n"
                "📋 **Your onboarding plan includes:**\n"
                "- Environment setup & access provisioning\n"
                "- Team introductions & culture overview\n"
                "- Codebase walkthrough & architecture review\n"
                "- First contribution guidance\n\n"
                "I'll track your progress and guide you through each step. "
                "Would you like to start with your first task?"
            )
        elif any(w in last_human for w in ["checklist", "task", "progress", "status"]):
            content = (
                "Let me check your onboarding progress...\n\n"
                "📊 I'm fetching your current checklist and progress data. "
                "I'll provide a summary of completed and pending tasks."
            )
        elif any(w in last_human for w in ["help", "stuck", "issue", "problem"]):
            content = (
                "I'm here to help! 💡\n\n"
                "Here are some things I can assist with:\n"
                "- **Check your progress** and recommend next steps\n"
                "- **Answer questions** about company policies, tools, or codebase\n"
                "- **Mark tasks complete** or update their status\n"
                "- **Search the knowledge base** for documentation\n\n"
                "What would you like help with?"
            )
        else:
            content = (
                "I understand your question. As your onboarding assistant, "
                "I'm here to help you get productive as quickly as possible.\n\n"
                "**Suggested next steps:**\n"
                "- Review your onboarding checklist\n"
                "- Check out the knowledge base for documentation\n"
                "- Ask me about team structure or coding standards\n\n"
                "Is there anything specific you'd like to know?"
            )

        # Check for tool calls in the messages
        if hasattr(messages[-1], 'additional_kwargs'):
            tool_calls = messages[-1].additional_kwargs.get('tool_calls', [])
            if tool_calls:
                content = "I've processed the tool results. " + content

        ai_msg = AIMessage(content=content)
        return ChatResult(generations=[ChatGeneration(message=ai_msg)])


_llm_instance: Optional[Runnable] = None
# The individual provider models behind _llm_instance, kept so each can be health-checked.
_provider_models: dict = {}
_active_provider_info: dict = {
    "provider": "mock",
    "model": "mock-llm",
    "status": "fallback",
    "error": None,
}

# "google" is accepted as an alias so LLM_FALLBACK_PROVIDER=google works as expected.
_PROVIDER_ALIASES = {"google": "gemini"}


def _normalize_provider(name: str) -> str:
    name = (name or "").lower().strip()
    return _PROVIDER_ALIASES.get(name, name)


def is_mock_llm() -> bool:
    """Check if the currently active LLM is the MockChatLLM fallback."""
    return _active_provider_info.get("status") == "fallback" or isinstance(_llm_instance, MockChatLLM)


def _build_provider(provider: str, temperature: float, is_primary: bool) -> tuple[Optional[BaseChatModel], str, Optional[str]]:
    """
    Construct one provider's chat model. Returns (model, model_name, error).

    A primary that has a fallback behind it gets a short timeout and a single
    retry, so quota/rate-limit failures hand off quickly instead of stalling.
    """
    fast_fail = {"max_retries": 1, "timeout": settings.LLM_PRIMARY_TIMEOUT} if is_primary else {}

    if provider == "nvidia":
        key, model = settings.NVIDIA_API_KEY, settings.NVIDIA_MODEL
        if not key or key.startswith("your-"):
            return None, model, "NVIDIA_API_KEY missing or placeholder"
        try:
            from langchain_openai import ChatOpenAI
            # Reasoning models think before answering by default; that adds a lot of
            # latency to routing/composition, so it is opt-in via NVIDIA_ENABLE_THINKING.
            extra_body = {"chat_template_kwargs": {"enable_thinking": settings.NVIDIA_ENABLE_THINKING}}
            return ChatOpenAI(
                model=model,
                api_key=key,
                base_url=settings.NVIDIA_BASE_URL,
                temperature=temperature,
                extra_body=extra_body,
                **fast_fail,
            ), model, None
        except Exception as e:
            logger.error("❌ NVIDIA initialization failed for model '%s': %s", model, e, exc_info=True)
            return None, model, f"NVIDIA error: {e}"

    if provider == "grok":
        key, model = settings.GROK_API_KEY, settings.GROK_MODEL
        if not key:
            return None, model, "GROK_API_KEY missing"
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model, api_key=key, base_url=settings.GROK_BASE_URL, temperature=temperature, **fast_fail
            ), model, None
        except Exception as e:
            logger.error("❌ Grok initialization failed for model '%s': %s", model, e, exc_info=True)
            return None, model, f"Grok error: {e}"

    if provider == "gemini":
        key = settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY
        model = settings.GEMINI_MODEL or "gemini-3.5-flash"
        if not key or key.startswith("sk-") or key.startswith("your-"):
            return None, model, "GEMINI_API_KEY / GOOGLE_API_KEY missing or invalid"
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            # The Gemini client retries 6 times by default, which stalls requests on quota errors.
            gemini_kwargs = {"max_retries": 1, "timeout": settings.LLM_PRIMARY_TIMEOUT} if is_primary else {"max_retries": 2}
            return ChatGoogleGenerativeAI(
                model=model, google_api_key=key, temperature=temperature, **gemini_kwargs
            ), model, None
        except Exception as e:
            logger.error("❌ Gemini initialization failed for model '%s': %s", model, e, exc_info=True)
            return None, model, f"Gemini error: {e}"

    if provider == "anthropic":
        key = getattr(settings, "ANTHROPIC_API_KEY", "")
        model = getattr(settings, "ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
        if not key:
            return None, model, "ANTHROPIC_API_KEY missing"
        try:
            ChatAnthropic = importlib.import_module("langchain_anthropic").ChatAnthropic
            return ChatAnthropic(
                model=model, anthropic_api_key=key, temperature=temperature, **fast_fail
            ), model, None
        except Exception as e:
            logger.error("❌ Anthropic initialization failed for model '%s': %s", model, e, exc_info=True)
            return None, model, f"Anthropic error: {e}"

    if provider == "openai":
        key, model = settings.OPENAI_API_KEY, settings.LLM_MODEL
        if not key or key.startswith("sk-your-"):
            return None, model, "OPENAI_API_KEY missing or placeholder"
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=model, api_key=key, temperature=temperature, **fast_fail), model, None
        except Exception as e:
            logger.error("❌ OpenAI initialization failed for model '%s': %s", model, e, exc_info=True)
            return None, model, f"OpenAI error: {e}"

    if provider in ("", "mock", "none"):
        return None, "", None
    return None, "", f"Unknown LLM provider '{provider}'"


def get_llm(temperature: float = 0.3) -> Runnable:
    """
    Get the chat model for LLM_PROVIDER, with LLM_FALLBACK_PROVIDER behind it.

    When both are configured, every call goes to the primary first and is retried
    on the fallback if it raises (rate limit, quota, timeout, 5xx). If only one
    can be initialized, that one is used alone. MockChatLLM is used only when
    MOCK_LLM_ENABLED=true and no real provider is available.
    Caches the instance for reuse.
    """
    global _llm_instance, _active_provider_info, _provider_models
    if _llm_instance is not None:
        return _llm_instance

    provider = _normalize_provider(settings.LLM_PROVIDER or "nvidia")
    fallback_provider = _normalize_provider(settings.LLM_FALLBACK_PROVIDER)
    if fallback_provider == provider:
        fallback_provider = ""

    fallback_model, fallback_name, fallback_error = (None, "", None)
    if fallback_provider:
        fallback_model, fallback_name, fallback_error = _build_provider(fallback_provider, temperature, is_primary=False)
    primary_model, primary_name, primary_error = _build_provider(
        provider, temperature, is_primary=fallback_model is not None
    )
    _provider_models = {provider: primary_model, fallback_provider: fallback_model}

    fallback_info = None
    if fallback_provider:
        fallback_info = {
            "provider": fallback_provider,
            "model": fallback_name,
            "status": "active" if fallback_model else "unavailable",
            "error": fallback_error,
        }

    if primary_model and fallback_model:
        _llm_instance = primary_model.with_fallbacks([fallback_model])
        _active_provider_info = {
            "provider": provider, "model": primary_name, "status": "active", "error": None, "fallback": fallback_info,
        }
        logger.info("✅ LLM Provider active: %s (%s), fallback: %s (%s)", provider, primary_name, fallback_provider, fallback_name)
        return _llm_instance
    if primary_model:
        _llm_instance = primary_model
        _active_provider_info = {
            "provider": provider, "model": primary_name, "status": "active", "error": None, "fallback": fallback_info,
        }
        logger.info("✅ LLM Provider active: %s (%s), no fallback available", provider, primary_name)
        return _llm_instance
    if fallback_model:
        _llm_instance = fallback_model
        _active_provider_info = {
            "provider": fallback_provider,
            "model": fallback_name,
            "status": "active",
            "error": f"Primary '{provider}' unavailable: {primary_error}",
            "fallback": None,
        }
        logger.warning(
            "⚠️ Primary LLM '%s' unavailable (%s); using fallback %s (%s)",
            provider, primary_error, fallback_provider, fallback_name,
        )
        return _llm_instance

    message = "; ".join(e for e in (primary_error, fallback_error) if e) or f"LLM provider '{provider}' is unavailable"
    if not settings.MOCK_LLM_ENABLED:
        _active_provider_info = {"provider": provider, "model": "", "status": "unavailable", "error": message}
        raise RuntimeError(f"Configured LLM is unavailable: {message}")

    logger.warning("Using explicitly enabled Mock LLM (MOCK_LLM_ENABLED=true).")
    _active_provider_info = {"provider": "mock", "model": "mock-llm", "status": "fallback", "error": message}
    _llm_instance = MockChatLLM()
    return _llm_instance


HEALTH_CACHE_SECONDS = 60
HEALTH_PROBE_TIMEOUT = 20
_health_cache: dict = {}


def _describe_failure(exc: BaseException) -> str:
    """Short, user-facing reason for a failed probe."""
    text = f"{type(exc).__name__}: {exc}"
    lowered = text.lower()
    if "429" in text or "resource_exhausted" in lowered or "quota" in lowered or "rate limit" in lowered:
        return "Quota or rate limit exceeded"
    if "401" in text or "403" in text or "unauthorized" in lowered or "invalid api key" in lowered or "permission" in lowered:
        return "API key rejected"
    if "404" in text or "not found" in lowered:
        return "Model not found for this account"
    if "timeout" in lowered or "timed out" in lowered:
        return "Timed out"
    return text[:160]


def _probe(model) -> tuple[str, Optional[str]]:
    """Send a tiny real request; returns (health, reason)."""
    import concurrent.futures
    from langchain_core.messages import HumanMessage

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(model.invoke, [HumanMessage(content="Reply with the single word OK.")])
        future.result(timeout=HEALTH_PROBE_TIMEOUT)
        return "ok", None
    except concurrent.futures.TimeoutError:
        return "failing", "Timed out"
    except Exception as exc:
        return "failing", _describe_failure(exc)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def check_llm_health(force: bool = False) -> dict:
    """
    Provider info plus a live health check of the primary and fallback models.

    Configuration alone can't reveal an exhausted quota or a revoked key, so each
    configured model gets one tiny real request. Results are cached briefly so the
    Settings page doesn't spend quota on every visit.
    """
    import time

    info = get_llm_provider_info()
    now = time.time()
    cached = _health_cache.get("result")
    if cached and not force and now - _health_cache.get("at", 0) < HEALTH_CACHE_SECONDS:
        return cached

    def with_health(entry: Optional[dict]) -> Optional[dict]:
        if not entry:
            return entry
        entry = dict(entry)
        model = _provider_models.get(entry.get("provider"))
        if entry.get("status") == "active" and model is not None:
            entry["health"], entry["health_error"] = _probe(model)
        else:
            entry["health"], entry["health_error"] = "unavailable", entry.get("error")
        return entry

    result = with_health(info)
    if info.get("fallback"):
        result["fallback"] = with_health(info["fallback"])
    result["checked_at"] = datetime.now(timezone.utc).isoformat()
    _health_cache.update(result=result, at=now)
    return result


def get_llm_provider_info() -> dict:
    """Get info about the current LLM provider."""
    # Ensure LLM has attempted initialization to have accurate status
    if _llm_instance is None:
        try:
            get_llm()
        except RuntimeError:
            # Status endpoints must expose unavailable configuration without
            # converting it into a fabricated successful provider.
            pass
    return dict(_active_provider_info)


def reset_llm():
    """Reset the cached LLM instance (useful for testing)."""
    global _llm_instance, _active_provider_info, _provider_models
    _llm_instance = None
    _provider_models = {}
    _health_cache.clear()
    _active_provider_info = {
        "provider": "mock",
        "model": "mock-llm",
        "status": "fallback",
        "error": None,
    }
