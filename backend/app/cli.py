"""Run one analysis end-to-end from the terminal (no API server needed).

    python -m app.cli "Analyse employment trends in the technology sector from 2020-2024" [--web]

Prints the agent timeline as it happens and the final Markdown report.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid

from app.core.events import event_bus
from app.db.init import create_schema, seed_internal
from app.db.models import Analysis
from app.db.session import SessionLocal
from app.runner.task_runner import runner


async def main(query: str, web: bool, answer: str | None) -> None:
    await create_schema()
    await seed_internal()
    run_id = str(uuid.uuid4())
    async with SessionLocal() as session:
        session.add(Analysis(id=run_id, query=query, status="queued", options={"web_context": web}))
        await session.commit()
    queue = event_bus.subscribe(run_id)
    runner.start(run_id, query, {"web_context": web})

    async def printer() -> None:
        while True:
            e = await queue.get()
            content = e.content
            text = (content.get("text") or content.get("tool") or content.get("state") or content.get("message")
                    or content.get("question") or "")
            if e.type == "action":
                text = f"{content['tool']}({json.dumps(content.get('input'))[:140]})"
            elif e.type == "observation":
                text = ("ERROR " if content.get("is_error") else "") + json.dumps(content.get("result"))[:160]
            print(f"[{e.seq:03d}] {e.agent:<11} {e.type:<13} {text}")

    task = asyncio.create_task(printer())
    await runner.tasks[run_id]
    async with SessionLocal() as session:
        analysis = await session.get(Analysis, run_id)
    if analysis.status == "awaiting_input":
        reply = answer or input("\nClarification needed. Your answer: ")
        runner.resume(run_id, reply)
        await runner.tasks[run_id]
        async with SessionLocal() as session:
            analysis = await session.get(Analysis, run_id)
    await asyncio.sleep(0.2)
    task.cancel()
    print("\n" + "=" * 80)
    print(f"status: {analysis.status}   cost: ${float(analysis.total_cost_usd or 0):.4f}")
    if analysis.result and analysis.result.get("markdown"):
        print(analysis.result["markdown"])
    elif analysis.error:
        print("error:", analysis.error)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--web", action="store_true", help="include web context")
    parser.add_argument("--answer", help="pre-supplied clarification answer")
    args = parser.parse_args()
    asyncio.run(main(args.query, args.web, args.answer))
