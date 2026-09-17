"""Repository interfaces (Step 4b) — the only way anything above touches storage.

One abstract repo per entity. Callers depend on these ABCs, never on a concrete
backend, so SQLite today and Postgres tomorrow are the same to them (principle 9,
Decision D3). The SQLite implementations live in `sqlite.py`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import Conversation, Event, Message, Task


class ConversationRepo(ABC):
    @abstractmethod
    def add(self, conversation: Conversation) -> None: ...

    @abstractmethod
    def get(self, conversation_id: str) -> Conversation | None: ...

    @abstractmethod
    def list(self) -> list[Conversation]: ...


class MessageRepo(ABC):
    @abstractmethod
    def add(self, message: Message) -> None: ...

    @abstractmethod
    def list_for_conversation(self, conversation_id: str) -> list[Message]: ...


class TaskRepo(ABC):
    @abstractmethod
    def add(self, task: Task) -> None: ...

    @abstractmethod
    def get(self, task_id: str) -> Task | None: ...

    @abstractmethod
    def save(self, task: Task) -> None:
        """Upsert — insert if new, else update (and bump updated_at at the call site)."""

    @abstractmethod
    def list(
        self, status: str | None = None, agent_id: str | None = None
    ) -> list[Task]: ...

    @abstractmethod
    def subtasks(self, parent_task_id: str) -> list[Task]: ...


class EventRepo(ABC):
    @abstractmethod
    def append(self, event: Event) -> None: ...

    @abstractmethod
    def list(
        self, after: str | None = None, limit: int | None = None, type: str | None = None
    ) -> list[Event]:
        """Chronological. `after` is an event id cursor; returns events after it."""
