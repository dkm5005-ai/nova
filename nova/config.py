"""Runtime configuration, loaded from the environment / a local .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()  # reads .env in the current directory if present


@dataclass
class Settings:
    openai_api_key: str | None
    openai_model: str
    max_tokens: int

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
            max_tokens=int(os.environ.get("NOVA_MAX_TOKENS", "1024")),
        )
