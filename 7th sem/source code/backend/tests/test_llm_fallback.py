"""Primary/fallback LLM wiring: NVIDIA first, Google Gemini when NVIDIA fails."""
import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import HumanMessage

from app.config import settings
from app.agent import llm_loader


class _FailingChatModel(FakeListChatModel):
    """Stands in for a primary provider that is rate limited or out of quota."""

    def _call(self, *args, **kwargs):
        raise RuntimeError("429 RESOURCE_EXHAUSTED")


@pytest.fixture
def providers(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "nvidia")
    monkeypatch.setattr(settings, "LLM_FALLBACK_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "MOCK_LLM_ENABLED", False)
    llm_loader.reset_llm()
    yield monkeypatch
    llm_loader.reset_llm()


def _stub_builders(monkeypatch, built: dict):
    def fake_build(provider, temperature, is_primary):
        model = built.get(provider)
        return model, f"{provider}-model", None if model else f"{provider} not configured"

    monkeypatch.setattr(llm_loader, "_build_provider", fake_build)


def test_fallback_answers_when_primary_call_fails(providers):
    _stub_builders(providers, {
        "nvidia": _FailingChatModel(responses=["unused"]),
        "gemini": FakeListChatModel(responses=["answer from gemini"]),
    })
    llm = llm_loader.get_llm()
    assert llm.invoke([HumanMessage(content="hi")]).content == "answer from gemini"

    info = llm_loader.get_llm_provider_info()
    assert info["provider"] == "nvidia"
    assert info["fallback"]["provider"] == "gemini"
    assert info["fallback"]["status"] == "active"


def test_primary_answers_when_healthy(providers):
    _stub_builders(providers, {
        "nvidia": FakeListChatModel(responses=["answer from nemotron"]),
        "gemini": FakeListChatModel(responses=["answer from gemini"]),
    })
    assert llm_loader.get_llm().invoke([HumanMessage(content="hi")]).content == "answer from nemotron"


def test_fallback_used_alone_when_primary_not_configured(providers):
    _stub_builders(providers, {"gemini": FakeListChatModel(responses=["answer from gemini"])})
    assert llm_loader.get_llm().invoke([HumanMessage(content="hi")]).content == "answer from gemini"

    info = llm_loader.get_llm_provider_info()
    assert info["provider"] == "gemini"
    assert "nvidia" in info["error"]


def test_unavailable_when_no_provider_configured(providers):
    _stub_builders(providers, {})
    with pytest.raises(RuntimeError, match="Configured LLM is unavailable"):
        llm_loader.get_llm()
    assert llm_loader.get_llm_provider_info()["status"] == "unavailable"


def test_google_is_accepted_as_fallback_alias(providers):
    providers.setattr(settings, "LLM_FALLBACK_PROVIDER", "google")
    _stub_builders(providers, {"gemini": FakeListChatModel(responses=["answer from gemini"])})
    llm_loader.get_llm()
    assert llm_loader.get_llm_provider_info()["provider"] == "gemini"


def test_nvidia_client_targets_nvidia_catalog_model(providers):
    providers.setattr(settings, "NVIDIA_API_KEY", "nvapi-test-key")
    providers.setattr(settings, "NVIDIA_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
    providers.setattr(settings, "NVIDIA_ENABLE_THINKING", False)
    model, name, error = llm_loader._build_provider("nvidia", 0.3, is_primary=True)

    assert error is None and name == "nvidia/nemotron-3.5-lightning-30b-a3b"
    assert model.model_name == "nvidia/nemotron-3.5-lightning-30b-a3b"
    assert model.openai_api_base == "https://integrate.api.nvidia.com/v1"
    assert model.extra_body == {"chat_template_kwargs": {"enable_thinking": False}}
    # A primary with a fallback behind it must fail fast rather than retry for minutes.
    assert model.max_retries == 1


def test_nvidia_missing_key_reports_error(providers):
    providers.setattr(settings, "NVIDIA_API_KEY", "")
    model, _, error = llm_loader._build_provider("nvidia", 0.3, is_primary=True)
    assert model is None
    assert "NVIDIA_API_KEY" in error


def test_api_key_pasted_with_bearer_prefix_is_cleaned():
    from app.config import strip_bearer_prefix

    assert strip_bearer_prefix("Bearer nvapi-abc123") == "nvapi-abc123"
    assert strip_bearer_prefix("  bearer   nvapi-abc123 ") == "nvapi-abc123"
    assert strip_bearer_prefix("nvapi-abc123") == "nvapi-abc123"


def test_display_name_instead_of_model_id_is_flagged(monkeypatch, caplog):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "nvidia")
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", "nvapi-test-key")
    monkeypatch.setattr(settings, "NVIDIA_MODEL", "Nemotron 3.5 Bolt E4B")
    with caplog.at_level("WARNING", logger="app.config"):
        settings.validate_configuration()
    assert "is not a model ID" in caplog.text

    caplog.clear()
    monkeypatch.setattr(settings, "NVIDIA_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
    with caplog.at_level("WARNING", logger="app.config"):
        settings.validate_configuration()
    assert "is not a model ID" not in caplog.text
