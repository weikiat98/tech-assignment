"""Provider-neutral ReAct loop: Thought -> Action -> Observation, streamed as AgentEvents.

The model returns a structured ReActStep (JSON), which works the same on OpenAI, Gemini
and the scripted MockLLM, and makes the "thought" explicit for the UI timeline.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from app.agents.prompts import REACT
from app.core.models import ReActStep
from app.core.run_context import RunContext
from app.llm.router import AllProvidersFailed, llm_router
from app.tools.base import Tool, truncate


def _render_history(goal: str, history: list[dict]) -> str:
    lines = [f"GOAL:\n{goal}\n"]
    for h in history:
        lines.append(f"Step {h['step']}\nThought: {h['thought']}\nAction: {h['action']} "
                     f"{json.dumps(h['input'], ensure_ascii=False)}\n"
                     f"Observation: {json.dumps(h['observation_short'], ensure_ascii=False, default=str)}\n")
    lines.append("Decide the next step.")
    return "\n".join(lines)


async def run_react(agent: str, goal: str, tools: list[Tool], ctx: RunContext,
                    mock_policy: Callable[[RunContext, list[dict]], ReActStep], extra: str,
                    max_steps: int = 12, callbacks: list | None = None) -> str:
    tool_map = {t.name: t for t in tools}
    system = REACT.format(agent=agent, extra=extra, tools="\n".join(t.spec() for t in tools))
    history: list[dict] = []
    for step in range(1, max_steps + 1):
        messages = [("system", system), ("user", _render_history(goal, history))]
        try:
            decision, result = await llm_router.structured(
                "react_step", agent, messages, ReActStep, ctx=ctx,
                mock_fn=lambda: mock_policy(ctx, history), callbacks=callbacks)
        except AllProvidersFailed as exc:
            await ctx.emit(agent, "error", {"step": step, "message": f"No LLM available: {exc}"})
            return f"Stopped: no LLM provider available ({exc})."
        tokens = result.prompt_tokens + result.completion_tokens
        await ctx.emit(agent, "thought", {"step": step, "text": decision.thought, "provider": result.provider},
                       tokens=tokens)
        if decision.action == "finish":
            await ctx.emit(agent, "status", {"state": "finished", "summary": decision.final_answer})
            return decision.final_answer or "Done."
        try:
            args = json.loads(decision.action_input_json or "{}")
        except json.JSONDecodeError:
            args = {}
        await ctx.emit(agent, "action", {"step": step, "tool": decision.action, "input": args})
        tool = tool_map.get(decision.action)
        observation = (await tool(ctx, args)) if tool else {"error": f"Unknown tool '{decision.action}'. "
                                                                     f"Available: {list(tool_map)}"}
        short = truncate(observation)
        await ctx.emit(agent, "observation", {"step": step, "tool": decision.action, "result": short,
                                              "is_error": isinstance(observation, dict) and "error" in observation})
        history.append({"step": step, "thought": decision.thought, "action": decision.action, "input": args,
                        "observation": observation, "observation_short": short})
    await ctx.emit(agent, "warning", {"kind": "step_budget", "message": f"Stopped after {max_steps} steps"})
    return f"Stopped at the {max_steps}-step budget; partial results kept."
