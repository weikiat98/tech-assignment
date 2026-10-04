"""Minimal tool abstraction for the ReAct loop: name, description, typed args, async function."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from app.core.run_context import RunContext

ToolFn = Callable[..., Awaitable[dict[str, Any]]]


@dataclass
class Tool:
    name: str
    description: str
    args: type[BaseModel]
    fn: ToolFn

    def spec(self) -> str:
        fields = []
        for fname, f in self.args.model_fields.items():
            ann = getattr(f.annotation, "__name__", str(f.annotation)).replace("typing.", "")
            req = "required" if f.is_required() else f"optional, default={f.default!r}"
            desc = f" - {f.description}" if f.description else ""
            fields.append(f"    {fname}: {ann} ({req}){desc}")
        return f"- {self.name}: {self.description}\n" + ("\n".join(fields) if fields else "    (no arguments)")

    async def __call__(self, ctx: RunContext, raw_args: str | dict[str, Any]) -> dict[str, Any]:
        try:
            data = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            args = self.args.model_validate(data or {})
        except (json.JSONDecodeError, ValidationError) as exc:
            return {"error": f"Invalid arguments for {self.name}: {str(exc)[:300]}"}
        try:
            return await self.fn(ctx, **args.model_dump())
        except Exception as exc:  # noqa: BLE001 - errors become observations so the agent can adapt
            return {"error": f"{type(exc).__name__}: {str(exc)[:400]}"}


def truncate(obj: Any, limit: int = 2500) -> Any:
    """Keep observations small enough for the prompt."""
    text = json.dumps(obj, default=str, ensure_ascii=False)
    if len(text) <= limit:
        return obj
    return {"truncated": True, "preview": text[:limit]}
