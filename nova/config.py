"""Runtime configuration, loaded from the environment / a local .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()  # reads .env in the current directory if present


@dataclass
class Settings:
    provider: str  # which vendor backs the agent: "openai" | "anthropic"
    openai_api_key: str | None
    openai_model: str
    anthropic_api_key: str | None
    anthropic_model: str
    max_tokens: int
    db_path: str  # where the SQLite state/memory store lives (never hardcoded)

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            provider=os.environ.get("NOVA_PROVIDER", "openai"),
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
            anthropic_model=os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8"),
            max_tokens=int(os.environ.get("NOVA_MAX_TOKENS", "1024")),
            # User-level dir outside any repo by default; `~` is expanded at connect.
            db_path=os.environ.get("NOVA_DB_PATH", "~/.nova/nova.db"),
        )
