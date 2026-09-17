"""Domain models the backend persists and the dashboard renders (Step 4a).

Plain dataclasses, mirroring the entities in `docs/DESIGN.md` §5 and the schemas
in `docs/API.md`. They are storage-agnostic: no SQL, no provider types. Each has
a `create()` classmethod that mints the id and timestamps so call sites stay
clean and ids are consistent (opaque `<prefix>_<hex>` strings, per API.md).

This package sits at the bottom of the dependency graph — it imports nothing from
`llm`, `tools`, `orchestrator`, or `api`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


def now_iso() -> str:
    """Current time as an ISO-8601 UTC string (the timestamp format API.md uses)."""
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    BLOCKED = "blocked"
    DONE = "done"
    FAILED = "failed"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


@dataclass
class Conversation:
    id: str
    title: str
    created_at: str

    @classmethod
    def create(cls, title: str) -> "Conversation":
        return cls(id=new_id("cnv"), title=title, created_at=now_iso())


@dataclass
class Message:
    id: str
    conversation_id: str
    role: str  # one of MessageRole
    text: str
    created_at: str
    agent_id: str | None = None
    tool_calls: list[dict] = field(default_factory=list)  # [{id, name, arguments}]

    @classmethod
    def create(
        cls,
        conversation_id: str,
        role: str | MessageRole,
        text: str,
        agent_id: str | None = None,
        tool_calls: list[dict] | None = None,
    ) -> "Message":
        return cls(
            id=new_id("msg"),
            conversation_id=conversation_id,
            role=str(role.value if isinstance(role, MessageRole) else role),
            text=text,
            created_at=now_iso(),
            agent_id=agent_id,
            tool_calls=list(tool_calls or []),
        )


@dataclass
class Task:
    id: str
    title: str
    description: str
    status: str  # one of TaskStatus
    created_at: str
    updated_at: str
    agent_id: str | None = None
    parent_task_id: str | None = None  # set for delegated subtasks
    conversation_id: str | None = None
    result: str | None = None
    error: str | None = None

    @classmethod
    def create(
        cls,
        title: str,
        description: str = "",
        agent_id: str | None = None,
        parent_task_id: str | None = None,
        conversation_id: str | None = None,
        status: str | TaskStatus = TaskStatus.QUEUED,
    ) -> "Task":
        ts = now_iso()
        return cls(
            id=new_id("task"),
            title=title,
            description=description,
            status=str(status.value if isinstance(status, TaskStatus) else status),
            created_at=ts,
            updated_at=ts,
            agent_id=agent_id,
            parent_task_id=parent_task_id,
            conversation_id=conversation_id,
        )


@dataclass
class Event:
    """Append-only activity record — the dashboard contract (see API.md)."""

    id: str
    type: str
    ts: str
    data: dict

    @classmethod
    def create(cls, type: str, data: dict | None = None) -> "Event":
        return cls(id=new_id("evt"), type=type, ts=now_iso(), data=dict(data or {}))
