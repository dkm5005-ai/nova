"""Pick LLM providers from config — the seam that makes vendor choice a knob.

Switching the model behind an agent is a one-line env change (`NOVA_PROVIDER`),
never a code change. Imports are lazy so you only need the SDK for the provider
you actually use.

`ProviderPool` extends this to the multi-agent world (Step 3): different agents
may run on different vendors, so the pool builds a provider per vendor name and
caches the client, and reports each vendor's configured default model.
"""

from __future__ import annotations

from ..config import Settings
from .base import LLMProvider


def provider_for(name: str, settings: Settings) -> LLMProvider:
    """Build the provider for a vendor name, or raise if its key is missing."""
    name = name.lower()

    if name == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set (see .env).")
        from .openai_provider import OpenAIProvider

        return OpenAIProvider(api_key=settings.openai_api_key)

    if name == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set (see .env).")
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider(api_key=settings.anthropic_api_key)

    raise RuntimeError(
        f"Unknown provider '{name}'. Use 'openai' or 'anthropic'."
    )


def default_model_for(name: str, settings: Settings) -> str:
    """The configured default model id for a vendor name."""
    name = name.lower()
    if name == "openai":
        return settings.openai_model
    if name == "anthropic":
        return settings.anthropic_model
    raise RuntimeError(f"Unknown provider '{name}'. Use 'openai' or 'anthropic'.")


def build_provider(settings: Settings) -> tuple[LLMProvider, str]:
    """Return the configured provider and the model id to run on it."""
    name = settings.provider.lower()
    return provider_for(name, settings), default_model_for(name, settings)


class ProviderPool:
    """Lazily builds and caches one provider per vendor, shared across agents.

    An agent definition names a vendor (or defaults to `NOVA_PROVIDER`); the pool
    hands back a shared client for that vendor so we open one connection per
    vendor, not one per agent.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._cache: dict[str, LLMProvider] = {}

    def _resolve(self, name: str | None) -> str:
        return (name or self._settings.provider).lower()

    def get(self, name: str | None = None) -> LLMProvider:
        resolved = self._resolve(name)
        if resolved not in self._cache:
            self._cache[resolved] = provider_for(resolved, self._settings)
        return self._cache[resolved]

    def model_for(self, name: str | None = None) -> str:
        return default_model_for(self._resolve(name), self._settings)
