"""Follow-up question suggestions (todo.md CL13), built deterministically from the answered intent.

No LLM call, so they cost nothing and can't introduce an out-of-scope question. Each one is phrased so the
follow-up interpreter resolves it from the earlier turn (sector, metric and years are inherited).
"""

from __future__ import annotations

from typing import Any

SECTOR_SHORT = {
    "Information And Communications": "technology",
    "Financial And Insurance Services": "finance and insurance",
    "Manufacturing": "manufacturing",
    "Construction": "construction",
    "Wholesale And Retail Trade": "wholesale and retail",
    "Accommodation And Food Services": "hospitality",
    "Transportation And Storage": "transport and storage",
    "Professional Services": "professional services",
}
OTHER_METRIC = {"employment": "retrenchments", "retrenchment": "employment", "vacancies": "employment",
                "compensation": "employment", "unemployment": "employment", "gdp": "employment",
                "programmes": "employment"}


def follow_ups(intent: dict[str, Any] | None, limit: int = 3) -> list[str]:
    if not intent or intent.get("out_of_scope"):
        return []
    sectors: list[str] = intent.get("sectors") or []
    metrics: list[str] = intent.get("metrics") or ["employment"]
    analysis: list[str] = intent.get("analysis_types") or []
    out: list[str] = []
    other = next((s for s in SECTOR_SHORT if s not in sectors), None)
    if other and sectors:
        out.append(f"What about {SECTOR_SHORT[other]}?")
    elif not sectors:
        out.append("Focus on the technology sector")
    if metrics and metrics[0] in OTHER_METRIC:
        out.append(f"How did {OTHER_METRIC[metrics[0]]} change over the same years?")
    if "forecast" not in analysis and "employment" in metrics:
        out.append("Forecast this for the next two years")
    if sectors and "comparison" not in analysis and len(sectors) == 1 and other:
        out.append(f"Compare with {SECTOR_SHORT[other]}")
    return list(dict.fromkeys(out))[:limit]
