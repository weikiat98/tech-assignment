"""Hallucination-detection evaluation: mutate verified claims from real runs, measure what the verifier catches.

Each sample query runs end to end (MockLLM + recorded snapshots). Every claim in its verified report is
a true negative; each mutation of a claim is a known hallucination. The verifier must flag every
mutation (recall) and none of the originals (false positives). Run with ``-s`` to print the table
that TESTING.md reports.
"""

import re
import uuid

import pytest

from app.core.models import Claim
from app.db.init import create_schema, seed_internal
from app.db.models import Analysis
from app.db.session import SessionLocal
from app.runner.task_runner import runner
from app.verification.checks import check_claim, extract_number_tokens

QUERIES = [
    "Analyse employment trends in the technology sector from 2020-2024",
    "Compare employment growth across sectors from 2019 to 2024",
    "How did workforce training programme enrolments relate to placements in the tech sector from 2019-2024?",
    "Forecast technology sector employment for the next two years",
]
SECTORS = ["Information And Communications", "Construction", "Manufacturing"]
YEAR = re.compile(r"\b(19|20)\d{2}\b")


def _perturb_number(c: Claim, ctx):
    for value, decimals, _pct, token in extract_number_tokens(c.text):
        if YEAR.fullmatch(token.lstrip("+-")):
            continue
        bumped = value * 1.1 if value else 1.0
        new = f"{bumped:,.{decimals}f}" if "," in token else f"{bumped:.{decimals}f}"
        if new == token.rstrip("%"):
            new = f"{value + 10 ** -decimals:.{decimals}f}"
        return c.model_copy(update={"text": c.text.replace(token.rstrip("%"), new, 1)})
    return None


def _append_fabrication(c: Claim, ctx):
    return c.model_copy(update={"text": c.text + " This rose by 37.5% in the final year alone."})


def _out_of_range_year(c: Claim, ctx):
    m = YEAR.search(c.text)
    return c.model_copy(update={"text": c.text[:m.start()] + "2035" + c.text[m.end():]}) if m else None


def _wrong_sector(c: Claim, ctx):
    for sector in SECTORS:
        if sector in c.text and extract_number_tokens(c.text):
            other = next(s for s in SECTORS if s != sector)
            return c.model_copy(update={"text": c.text.replace(sector, other)})
    return None


def _unknown_fact_id(c: Claim, ctx):
    return c.model_copy(update={"fact_ids": [*c.fact_ids, "F999"]})


def _drop_citations(c: Claim, ctx):
    has_number = any(not YEAR.fullmatch(t.lstrip("+-")) for *_, t in extract_number_tokens(c.text))
    return c.model_copy(update={"fact_ids": []}) if has_number and c.fact_ids else None


def _wrong_citation(c: Claim, ctx):
    cited = {ctx.facts[i].value for i in c.fact_ids if i in ctx.facts}
    other = next((f for f in ctx.facts.values() if f.id not in c.fact_ids and f.method == "level"
                  and all(abs(f.value - v) > 1 for v in cited)), None)
    has_number = any(not YEAR.fullmatch(t.lstrip("+-")) for *_, t in extract_number_tokens(c.text))
    return c.model_copy(update={"fact_ids": [other.id]}) if other and has_number else None


MUTATIONS = {
    "perturbed number (+10%)": _perturb_number,
    "fabricated extra sentence": _append_fabrication,
    "year outside the data": _out_of_range_year,
    "right numbers, wrong sector": _wrong_sector,
    "citation to a missing fact": _unknown_fact_id,
    "numeric claim, citations removed": _drop_citations,
    "cites an unrelated fact": _wrong_citation,
}


async def _run(query: str):
    run_id = str(uuid.uuid4())
    async with SessionLocal() as session:
        session.add(Analysis(id=run_id, query=query, status="queued", options={}))
        await session.commit()
    runner.start(run_id, query, {})
    await runner.tasks[run_id]
    async with SessionLocal() as session:
        analysis = await session.get(Analysis, run_id)
    return analysis.result, runner.contexts[run_id]


@pytest.mark.eval
async def test_verifier_catches_every_mutation_without_false_positives():
    await create_schema()
    await seed_internal()
    originals, caught, total = 0, dict.fromkeys(MUTATIONS, 0), dict.fromkeys(MUTATIONS, 0)
    false_positives = []
    for query in QUERIES:
        result, ctx = await _run(query)
        report = result["report"]
        for section in ("key_findings", "sector_analysis", "policy_implications"):
            for raw in report[section]:
                claim = Claim(**raw)
                originals += 1
                if not check_claim(claim, section, ctx).passed:
                    false_positives.append(claim.text)
                for name, mutate in MUTATIONS.items():
                    mutated = mutate(claim, ctx)
                    if mutated is None:
                        continue
                    total[name] += 1
                    caught[name] += not check_claim(mutated, section, ctx).passed

    rows = [f"| {name} | {total[name]} | {caught[name]} | {caught[name] / total[name]:.0%} |"
            for name in MUTATIONS if total[name]]
    all_caught, all_total = sum(caught.values()), sum(total.values())
    print("\n| Hallucination injected | Mutated claims | Flagged | Recall |\n|---|---|---|---|")
    print("\n".join(rows))
    print(f"| **All** | **{all_total}** | **{all_caught}** | **{all_caught / all_total:.0%}** |")
    print(f"\nUnmodified claims: {originals}, wrongly flagged: {len(false_positives)}")

    assert not false_positives, false_positives
    assert all(total.values()), total  # every mutation type was exercised
    assert all_caught == all_total, {k: (caught[k], total[k]) for k in MUTATIONS}
