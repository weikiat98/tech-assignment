"""End-to-end runs of the LangGraph pipeline on the scripted MockLLM and recorded source snapshots.

These go through the real task runner (the same path the API uses), so they cover interpretation,
planning, extraction tools, quality gate, analytics, writing, verification and persistence.
"""

import uuid

import pytest
from sqlalchemy import select

from app.core.chaos import chaos
from app.db.init import create_schema, seed_internal
from app.db.models import AgentEventRow, Analysis
from app.db.session import SessionLocal
from app.runner.task_runner import runner

MAIN = "Analyse employment trends in the technology sector from 2020-2024"


@pytest.fixture(autouse=True)
async def db():
    await create_schema()
    await seed_internal()


async def run(query: str, answer: str | None = None) -> tuple[Analysis, list[AgentEventRow]]:
    run_id = str(uuid.uuid4())
    async with SessionLocal() as session:
        session.add(Analysis(id=run_id, query=query, status="queued", options={}))
        await session.commit()
    runner.start(run_id, query, {})
    await runner.tasks[run_id]
    if answer is not None:
        async with SessionLocal() as session:
            assert (await session.get(Analysis, run_id)).status == "awaiting_input"
        assert runner.resume(run_id, answer)
        await runner.tasks[run_id]
    async with SessionLocal() as session:
        analysis = await session.get(Analysis, run_id)
        events = (await session.scalars(select(AgentEventRow).where(AgentEventRow.analysis_id == run_id)
                                        .order_by(AgentEventRow.seq))).all()
    return analysis, list(events)


def of_type(events, kind):
    return [e for e in events if e.type == kind]


async def test_main_demo_query_end_to_end():
    analysis, events = await run(MAIN)
    assert analysis.status == "completed", analysis.error
    result = analysis.result
    assert result["verification"]["passed"]
    assert result["verification"]["numeric_pass_rate"] == 1.0
    assert len(result["facts"]) >= 10 and len(result["charts"]) >= 3
    sources = {d["source_id"] for d in result["datasets"]}
    assert {"singstat", "mom", "datagov"} <= sources  # at least two government sources, as the brief asks
    assert "Information And Communications" in result["markdown"]
    # Every ReAct step is visible: thoughts, actions and observations for both agents.
    for kind in ("thought", "action", "observation", "quality", "fact", "chart", "verification", "final"):
        assert of_type(events, kind), kind
    assert {e.agent for e in of_type(events, "action")} == {"extraction", "analytics"}


async def test_every_report_number_traces_to_a_fact():
    analysis, _ = await run(MAIN)
    result = analysis.result
    fact_ids = {f["id"] for f in result["facts"]}
    for check in result["verification"]["checks"]:
        assert check["passed"], check
    claims = result["report"]["key_findings"]
    assert claims and all(set(c["fact_ids"]) <= fact_ids for c in claims)


async def test_same_query_twice_gives_identical_facts():
    a, _ = await run(MAIN)
    b, _ = await run(MAIN)
    facts = lambda r: sorted((f["key"], round(f["value"], 9)) for f in r.result["facts"])  # noqa: E731
    assert facts(a) == facts(b)


async def test_injected_hallucination_is_caught_and_rewritten():
    chaos.inject_hallucination = True
    analysis, events = await run(MAIN)
    verifications = [e.content for e in of_type(events, "verification")]
    assert len(verifications) == 2
    assert not verifications[0]["passed"]
    assert any("37.5" in f for f in verifications[0]["failing"])
    assert verifications[1]["passed"]
    assert "37.5%" not in analysis.result["markdown"]


async def test_clarification_interrupt_and_resume():
    analysis, events = await run("How is the job market doing?", answer="Technology sector employment, 2020 to 2024")
    assert of_type(events, "clarification")
    assert analysis.status == "completed"
    assert analysis.result["verification"]["passed"]


async def test_correlation_with_internal_programme_data():
    analysis, _ = await run("How did workforce training programme enrolments relate to placements in the tech "
                            "sector from 2019-2024?")
    methods = {f["method"] for f in analysis.result["facts"]}
    assert {"pearson", "spearman"} <= methods
    assert any("synthetic" in x.lower() for x in analysis.result["report"]["limitations"])


async def test_forecast_is_labelled_as_projection():
    analysis, _ = await run("Forecast technology sector employment for the next two years")
    projections = [f for f in analysis.result["facts"] if f["method"] == "linear_projection"]
    assert len(projections) == 2
    assert "projection" in analysis.result["markdown"].lower()


async def test_source_outage_degrades_gracefully():
    chaos.fail_sources = {"singstat_mcp", "singstat_rest", "datagov"}
    analysis, events = await run(MAIN)
    assert analysis.status == "completed"
    assert of_type(events, "fallback")
    assert analysis.result["verification"]["passed"]
    assert any("snapshot" in x for x in analysis.result["report"]["limitations"])


async def test_retrenchment_question_annualises_quarterly_data():
    analysis, events = await run("Why did retrenchments in the technology sector rise in 2023?")
    assert any(e.content.get("tool") == "annualise" for e in of_type(events, "action"))
    assert analysis.result["verification"]["passed"]
    assert any(f["source_keys"][0].endswith("~annual") for f in analysis.result["facts"])


async def test_clarified_metric_is_the_one_analysed():
    """Answering the clarification with 'retrenchments' must analyse retrenchments, not employment."""
    analysis, _ = await run("How is the job market doing?", answer="Retrenchments in the technology sector, 2019-2024")
    findings = " ".join(c["text"] for c in analysis.result["report"]["key_findings"])
    assert findings.startswith("Retrenchments in Information And Communications")
    assert all(f["source_keys"][0].startswith("singstat:M183881") for f in analysis.result["facts"]
               if f["method"] == "level")
