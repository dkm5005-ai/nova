"""SQLite implementations of the repositories + the store that wires them (Step 4b).

`SqliteStore(path)` opens (and creates) the database, applies the schema, and
exposes one repo per entity. It's the only file here that speaks SQL; swapping to
Postgres later means a sibling `postgres.py`, nothing above changes (D3).

Serialization: dicts/lists (`Message.tool_calls`, `Event.data`) are stored as JSON
text. Events carry an autoincrement `seq` for stable chronological order and the
`after` cursor; the opaque event id is what callers pass, resolved to its seq.

Threading: a single connection with `check_same_thread=False` guarded by a lock,
so the Step-5 async API (agent runs in worker threads, D4) can share one store.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from .models import Conversation, Event, Message, Task
from .repositories import ConversationRepo, EventRepo, MessageRepo, TaskRepo

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id               TEXT PRIMARY KEY,
    conversation_id  TEXT NOT NULL REFERENCES conversations(id),
    role             TEXT NOT NULL,
    text             TEXT NOT NULL,
    agent_id         TEXT,
    tool_calls       TEXT NOT NULL DEFAULT '[]',
    created_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE TABLE IF NOT EXISTS tasks (
    id               TEXT PRIMARY KEY,
    title            TEXT NOT NULL,
    description      TEXT NOT NULL DEFAULT '',
    status           TEXT NOT NULL,
    agent_id         TEXT,
    parent_task_id   TEXT,
    conversation_id  TEXT,
    result           TEXT,
    error            TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_agent ON tasks(agent_id);
CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_task_id);
CREATE TABLE IF NOT EXISTS events (
    seq   INTEGER PRIMARY KEY AUTOINCREMENT,
    id    TEXT NOT NULL UNIQUE,
    type  TEXT NOT NULL,
    ts    TEXT NOT NULL,
    data  TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
"""


def connect(path: str) -> sqlite3.Connection:
    """Open a connection to the db at `path`, creating the parent dir as needed."""
    resolved = Path(path).expanduser()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(resolved), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


class SqliteStore:
    """Owns the connection + schema, and exposes the four repositories."""

    def __init__(self, path: str):
        self.path = path
        self._conn = connect(path)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
        self.conversations = _SqliteConversationRepo(self._conn, self._lock)
        self.messages = _SqliteMessageRepo(self._conn, self._lock)
        self.tasks = _SqliteTaskRepo(self._conn, self._lock)
        self.events = _SqliteEventRepo(self._conn, self._lock)

    def close(self) -> None:
        with self._lock:
            self._conn.close()


class _Base:
    def __init__(self, conn: sqlite3.Connection, lock: threading.Lock):
        self._conn = conn
        self._lock = lock

    def _write(self, sql: str, params: tuple) -> None:
        with self._lock:
            self._conn.execute(sql, params)
            self._conn.commit()

    def _query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._conn.execute(sql, params))


class _SqliteConversationRepo(_Base, ConversationRepo):
    def add(self, c: Conversation) -> None:
        self._write(
            "INSERT INTO conversations (id, title, created_at) VALUES (?, ?, ?)",
            (c.id, c.title, c.created_at),
        )

    def get(self, conversation_id: str) -> Conversation | None:
        rows = self._query(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        )
        return _conversation(rows[0]) if rows else None

    def list(self) -> list[Conversation]:
        rows = self._query("SELECT * FROM conversations ORDER BY created_at")
        return [_conversation(r) for r in rows]


class _SqliteMessageRepo(_Base, MessageRepo):
    def add(self, m: Message) -> None:
        self._write(
            "INSERT INTO messages (id, conversation_id, role, text, agent_id, "
            "tool_calls, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                m.id,
                m.conversation_id,
                m.role,
                m.text,
                m.agent_id,
                json.dumps(m.tool_calls),
                m.created_at,
            ),
        )

    def list_for_conversation(self, conversation_id: str) -> list[Message]:
        rows = self._query(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at, id",
            (conversation_id,),
        )
        return [_message(r) for r in rows]


class _SqliteTaskRepo(_Base, TaskRepo):
    _COLS = (
        "id, title, description, status, agent_id, parent_task_id, "
        "conversation_id, result, error, created_at, updated_at"
    )

    def _params(self, t: Task) -> tuple:
        return (
            t.id, t.title, t.description, t.status, t.agent_id, t.parent_task_id,
            t.conversation_id, t.result, t.error, t.created_at, t.updated_at,
        )

    def add(self, t: Task) -> None:
        self._write(
            f"INSERT INTO tasks ({self._COLS}) VALUES ({', '.join('?' * 11)})",
            self._params(t),
        )

    def save(self, t: Task) -> None:
        self._write(
            "INSERT INTO tasks (" + self._COLS + ") "
            f"VALUES ({', '.join('?' * 11)}) "
            "ON CONFLICT(id) DO UPDATE SET "
            "title=excluded.title, description=excluded.description, "
            "status=excluded.status, agent_id=excluded.agent_id, "
            "parent_task_id=excluded.parent_task_id, "
            "conversation_id=excluded.conversation_id, result=excluded.result, "
            "error=excluded.error, updated_at=excluded.updated_at",
            self._params(t),
        )

    def get(self, task_id: str) -> Task | None:
        rows = self._query("SELECT * FROM tasks WHERE id = ?", (task_id,))
        return _task(rows[0]) if rows else None

    def list(
        self, status: str | None = None, agent_id: str | None = None
    ) -> list[Task]:
        clauses, params = [], []
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if agent_id is not None:
            clauses.append("agent_id = ?")
            params.append(agent_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._query(
            f"SELECT * FROM tasks{where} ORDER BY created_at", tuple(params)
        )
        return [_task(r) for r in rows]

    def subtasks(self, parent_task_id: str) -> list[Task]:
        rows = self._query(
            "SELECT * FROM tasks WHERE parent_task_id = ? ORDER BY created_at",
            (parent_task_id,),
        )
        return [_task(r) for r in rows]


class _SqliteEventRepo(_Base, EventRepo):
    def append(self, e: Event) -> None:
        self._write(
            "INSERT INTO events (id, type, ts, data) VALUES (?, ?, ?, ?)",
            (e.id, e.type, e.ts, json.dumps(e.data)),
        )

    def list(
        self, after: str | None = None, limit: int | None = None, type: str | None = None
    ) -> list[Event]:
        clauses, params = [], []
        if after is not None:
            # Resolve the cursor id to its seq, then return strictly later rows.
            clauses.append("seq > (SELECT seq FROM events WHERE id = ?)")
            params.append(after)
        if type is not None:
            clauses.append("type = ?")
            params.append(type)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM events{where} ORDER BY seq"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        return [_event(r) for r in self._query(sql, tuple(params))]


# --- row -> model ---

def _conversation(r: sqlite3.Row) -> Conversation:
    return Conversation(id=r["id"], title=r["title"], created_at=r["created_at"])


def _message(r: sqlite3.Row) -> Message:
    return Message(
        id=r["id"],
        conversation_id=r["conversation_id"],
        role=r["role"],
        text=r["text"],
        created_at=r["created_at"],
        agent_id=r["agent_id"],
        tool_calls=json.loads(r["tool_calls"]),
    )


def _task(r: sqlite3.Row) -> Task:
    return Task(
        id=r["id"],
        title=r["title"],
        description=r["description"],
        status=r["status"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
        agent_id=r["agent_id"],
        parent_task_id=r["parent_task_id"],
        conversation_id=r["conversation_id"],
        result=r["result"],
        error=r["error"],
    )


def _event(r: sqlite3.Row) -> Event:
    return Event(id=r["id"], type=r["type"], ts=r["ts"], data=json.loads(r["data"]))
