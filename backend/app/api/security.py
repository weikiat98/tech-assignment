"""Shared access token for deployed environments (plan.md §11.1).

Off when APP_ACCESS_TOKEN is a placeholder (local dev). Accepted as
``Authorization: Bearer <token>``, ``X-Access-Token`` or ``?token=`` (WebSocket and download links).
"""

import hmac

from fastapi import HTTPException, Request, WebSocket, status

from app.config import get_settings, is_configured


def token_required() -> bool:
    return is_configured(get_settings().app_access_token)


def _valid(candidate: str | None) -> bool:
    return bool(candidate) and hmac.compare_digest(candidate, get_settings().app_access_token)


def _extract(headers, query_params) -> str | None:
    auth = headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return headers.get("x-access-token") or query_params.get("token")


async def require_token(request: Request) -> None:
    if token_required() and not _valid(_extract(request.headers, request.query_params)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token required")


def websocket_allowed(ws: WebSocket) -> bool:
    return not token_required() or _valid(_extract(ws.headers, ws.query_params))
