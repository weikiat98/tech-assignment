"""Health, configuration, provider/source status and chaos toggles."""

from __future__ import annotations

import asyncio

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from app.api.schemas import ChaosUpdate
from app.api.security import require_token, token_required
from app.config import get_settings
from app.core.chaos import chaos
from app.db.session import engine
from app.llm.router import llm_router
from app.observability import langfuse as lf
from app.web.search import provider_chain

public = APIRouter(tags=["meta"])
router = APIRouter(prefix="/api/v1", tags=["meta"], dependencies=[Depends(require_token)])

SAMPLE_QUERIES = [
    "Analyse employment trends in the technology sector from 2020-2024",
    "Compare employment growth across sectors from 2019 to 2024",
    "Why did retrenchments in the technology sector rise in 2023? What did MOM say?",
    "How did workforce training programme enrolments relate to placements in the tech sector from 2019-2024?",
    "Forecast technology sector employment for the next two years",
    "How is the job market doing?",
]


@public.get("/healthz")
async def healthz():
    return {"status": "ok"}


@public.get("/readyz")
async def readyz():
    checks = {}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc}"
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{get_settings().gotenberg_url}/health")
        checks["gotenberg"] = "ok" if resp.status_code == 200 else f"status {resp.status_code}"
    except Exception:  # noqa: BLE001 - PDF export is optional for readiness
        checks["gotenberg"] = "unavailable (PDF export disabled)"
    ready = checks["database"] == "ok"
    return {"ready": ready, "checks": checks}


@public.get("/api/v1/public-config")
async def public_config():
    s = get_settings()
    return {"token_required": token_required(), "llm_mode": s.llm_mode, "version": s.app_version,
            "env": s.app_env, "sample_queries": SAMPLE_QUERIES}


@router.get("/config")
async def config():
    s = get_settings()
    return {"llm_chain": llm_router.chain(), "web_search_chain": [p.name for p in provider_chain()],
            "langfuse_enabled": lf.enabled(), "offline_mode": s.offline_mode, "chaos": chaos.as_dict()}


@router.get("/llm/providers")
async def llm_providers():
    return {"chain": llm_router.chain(), "providers": llm_router.status()}


@router.get("/sources/health")
async def sources_health():
    s = get_settings()

    async def probe(name: str, method: str, url: str, **kw) -> tuple[str, str]:
        try:
            async with httpx.AsyncClient(timeout=6) as client:
                resp = await client.request(method, url, **kw)
            return name, "ok" if resp.status_code < 500 else f"status {resp.status_code}"
        except Exception as exc:  # noqa: BLE001
            return name, f"unreachable: {type(exc).__name__}"

    mcp_init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                           "clientInfo": {"name": "health", "version": "0"}}}
    results = await asyncio.gather(
        probe("singstat_mcp", "POST", s.singstat_mcp_url, json=mcp_init,
              headers={"Accept": "application/json, text/event-stream"}),
        probe("datagov", "GET", f"{s.datagov_api_base}/datasets", params={"page": 1}),
        probe("mom_stats", "GET", "https://stats.mom.gov.sg"),
    )
    status = dict(results)
    status["internal"] = "ok"
    for name in chaos.fail_sources:
        status[name] = "chaos: simulated outage"
    return {"offline_mode": s.offline_mode, "sources": status}


@router.get("/admin/chaos")
async def get_chaos():
    return {**chaos.as_dict(), "enabled": get_settings().chaos_admin_allowed}


@router.put("/admin/chaos")
async def set_chaos(update: ChaosUpdate):
    if not get_settings().chaos_admin_allowed:
        raise HTTPException(status_code=403, detail="Chaos toggles are disabled on this deployment "
                                                    "(set CHAOS_ADMIN_ENABLED=true to allow them)")
    if update.fail_sources is not None:
        chaos.fail_sources = set(update.fail_sources)
    if update.fail_llm is not None:
        chaos.fail_llm = set(update.fail_llm)
    if update.inject_hallucination is not None:
        chaos.inject_hallucination = update.inject_hallucination
    return {**chaos.as_dict(), "enabled": True}
