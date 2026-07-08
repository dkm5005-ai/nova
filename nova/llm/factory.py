"""Pick the LLM provider from config — the seam that makes vendor choice a knob.

Switching the model behind an agent is a one-line env change (`NOVA_PROVIDER`),
never a code change. Imports are lazy so you only need the SDK for the provider
you actually use.
"""

from __future__ import annotations

from ..config import Settings
from .base import LLMProvider


def build_provider(settings: Settings) -> tuple[LLMProvider, str]:
    """Return the configured provider and the model id to run on it."""
    name = settings.provider.lower()

    if name == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set (see .env).")
        from .openai_provider import OpenAIProvider

        return OpenAIProvider(api_key=settings.openai_api_key), settings.openai_model

    if name == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set (see .env).")
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider(api_key=settings.anthropic_api_key), settings.anthropic_model

    raise RuntimeError(
        f"Unknown NOVA_PROVIDER '{settings.provider}'. Use 'openai' or 'anthropic'."
    )
