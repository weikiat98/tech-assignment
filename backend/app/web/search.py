"""Provider-neutral web search: Tavily -> DuckDuckGo -> (explicit) mock fixtures."""

from __future__ import annotations

import asyncio
from typing import Protocol

import httpx

from app.config import get_settings
from app.web.trust import trust_tier


class SearchResult(dict):
    """{'title', 'url', 'snippet', 'trust_tier', 'provider'}"""


class WebSearchProvider(Protocol):
    name: str

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]: ...


class TavilyProvider:
    name = "tavily"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"query": query, "max_results": max_results, "search_depth": "basic"},
            )
            resp.raise_for_status()
        return [SearchResult(title=r.get("title", ""), url=r["url"], snippet=r.get("content", "")[:400],
                             trust_tier=trust_tier(r["url"]), provider=self.name)
                for r in resp.json().get("results", [])]


class DuckDuckGoProvider:
    name = "ddg"

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        from ddgs import DDGS  # imported lazily: optional, keyless fallback

        def _run() -> list[dict]:
            return list(DDGS().text(query, max_results=max_results, region="sg-en"))

        hits = await asyncio.to_thread(_run)
        return [SearchResult(title=h.get("title", ""), url=h.get("href", ""), snippet=h.get("body", "")[:400],
                             trust_tier=trust_tier(h.get("href", "")), provider=self.name)
                for h in hits if h.get("href")]


class MockProvider:
    """Deterministic fixtures for tests, CI and offline demos."""

    name = "mock"
    FIXTURES = [
        SearchResult(title="Labour Market Report - Ministry of Manpower",
                     url="https://stats.mom.gov.sg/Pages/Labour-Market-Report.aspx",
                     snippet="Quarterly labour market report covering employment, unemployment and retrenchment.",
                     trust_tier=1, provider="mock"),
        SearchResult(title="Infocomm Media Industry Statistics - IMDA",
                     url="https://www.imda.gov.sg/about-imda/research-and-statistics",
                     snippet="Annual survey statistics on infocomm media manpower and revenue.",
                     trust_tier=1, provider="mock"),
        SearchResult(title="Tech layoffs in Singapore (news)",
                     url="https://example-news.com/sg-tech-layoffs",
                     snippet="News coverage of technology sector layoffs in Singapore.",
                     trust_tier=3, provider="mock"),
    ]

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        return self.FIXTURES[:max_results]


def provider_chain() -> list[WebSearchProvider]:
    settings = get_settings()
    choice = settings.web_search_provider
    if choice == "mock":
        return [MockProvider()]
    chain: list[WebSearchProvider] = []
    if choice in ("auto", "tavily") and settings.tavily_configured:
        chain.append(TavilyProvider(settings.tavily_api_key))
    if choice in ("auto", "ddg", "tavily"):
        chain.append(DuckDuckGoProvider())
    return chain


async def web_search(query: str, max_results: int = 5) -> tuple[list[SearchResult], list[str]]:
    """Return (results, errors). Tries each provider in order; empty results if all fail."""
    errors: list[str] = []
    for provider in provider_chain():
        try:
            results = await provider.search(query, max_results)
            if results:
                return results, errors
            errors.append(f"{provider.name}: no results")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{provider.name}: {type(exc).__name__}: {str(exc)[:120]}")
    return [], errors
