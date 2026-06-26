"""Nova's first real tools: read-only filesystem access, sandboxed to the project.

Both tools refuse any path that resolves outside the project root, so the agent
can inspect its own project but cannot wander the disk.
"""

from __future__ import annotations

from pathlib import Path

from ..llm.base import ToolSpec
from .base import Tool

ROOT = Path.cwd().resolve()


def _safe(path: str) -> Path:
    resolved = (ROOT / path).resolve()
    if resolved != ROOT and ROOT not in resolved.parents:
        raise ValueError(f"path '{path}' escapes the project directory")
    return resolved


def _list_files(args: dict) -> str:
    target = _safe(args.get("path", "."))
    if not target.exists():
        return f"No such path: {args.get('path', '.')}"
    if target.is_file():
        return target.name
    entries = sorted(
        p.name + ("/" if p.is_dir() else "") for p in target.iterdir()
    )
    return "\n".join(entries) if entries else "(empty directory)"


def _read_file(args: dict) -> str:
    target = _safe(args["path"])
    if not target.is_file():
        return f"Not a file: {args['path']}"
    return target.read_text(errors="replace")[:10_000]  # cap to protect context


list_files = Tool(
    spec=ToolSpec(
        name="list_files",
        description="List files and folders at a path inside the project. Use '.' for the project root.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path from the project root.",
                }
            },
        },
    ),
    handler=_list_files,
)

read_file = Tool(
    spec=ToolSpec(
        name="read_file",
        description="Read the text contents of a file inside the project (first 10k chars).",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the file.",
                }
            },
            "required": ["path"],
        },
    ),
    handler=_read_file,
)

DEFAULT_TOOLS = [list_files, read_file]
