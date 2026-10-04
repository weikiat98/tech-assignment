"""SSRF-safe page fetching and content extraction (plan.md §5.4)."""

from __future__ import annotations

import asyncio
import io
import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx
import pandas as pd

from app.config import get_settings

ALLOWED_CONTENT_TYPES = ("text/html", "text/plain", "text/csv", "application/json", "application/pdf",
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         "application/vnd.ms-excel", "application/xhtml+xml")
# Explicitly listed because they are the most valuable SSRF targets on AWS.
BLOCKED_HOSTS = {"169.254.169.254", "169.254.170.2", "metadata.google.internal", "localhost"}
MAX_REDIRECTS = 3
USER_AGENT = "policy-analytics-research-bot/0.1 (+https://github.com/; research use)"


class UnsafeURLError(ValueError):
    pass


async def assert_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError(f"scheme '{parsed.scheme}' not allowed")
    host = (parsed.hostname or "").lower()
    if not host or host in BLOCKED_HOSTS:
        raise UnsafeURLError(f"host '{host}' is blocked")
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"cannot resolve '{host}'") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified):
            raise UnsafeURLError(f"host '{host}' resolves to non-public address {ip}")


async def safe_fetch(url: str) -> tuple[bytes, str, str]:
    """Fetch a public URL with redirect re-validation, size and type limits.

    Returns (content, content_type, final_url).
    """
    settings = get_settings()
    current = url
    async with httpx.AsyncClient(timeout=settings.web_fetch_timeout_s, follow_redirects=False,
                                 headers={"User-Agent": USER_AGENT}) as client:
        for _ in range(MAX_REDIRECTS + 1):
            await assert_public_url(current)
            async with client.stream("GET", current) as resp:
                if resp.is_redirect:
                    current = urljoin(current, resp.headers.get("location", ""))
                    continue
                resp.raise_for_status()
                ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                if ctype and not ctype.startswith(ALLOWED_CONTENT_TYPES):
                    raise UnsafeURLError(f"content-type '{ctype}' not allowed")
                chunks, size = [], 0
                async for chunk in resp.aiter_bytes():
                    size += len(chunk)
                    if size > settings.web_fetch_max_bytes:
                        raise UnsafeURLError("response exceeds size limit")
                    chunks.append(chunk)
                return b"".join(chunks), ctype, current
    raise UnsafeURLError("too many redirects")


def extract_content(content: bytes, content_type: str, url: str) -> dict:
    """Main text + tables + links to data files from fetched content."""
    text, tables, data_links = "", [], []
    if "html" in content_type or content.lstrip()[:15].lower().startswith((b"<!doctype", b"<html")):
        html = content.decode("utf-8", errors="replace")
        try:
            import trafilatura

            text = trafilatura.extract(html, include_tables=True) or ""
        except Exception:  # noqa: BLE001 - extraction is best-effort
            text = ""
        try:
            tables = [t for t in pd.read_html(io.StringIO(html)) if not t.empty][:5]
        except (ValueError, ImportError):
            tables = []
        for href in _hrefs(html):
            absolute = urljoin(url, href)
            if absolute.lower().split("?")[0].endswith((".csv", ".xlsx", ".xls")):
                data_links.append(absolute)
    elif "csv" in content_type:
        tables = [pd.read_csv(io.BytesIO(content))]
        text = content.decode("utf-8", errors="replace")[:20000]
    elif "spreadsheet" in content_type or "excel" in content_type:
        tables = [pd.read_excel(io.BytesIO(content))]
        text = "\n".join(t.to_csv(index=False) for t in tables)[:20000]
    else:
        text = content.decode("utf-8", errors="replace")[:20000]
    return {"text": text[:50000], "tables": tables, "data_links": sorted(set(data_links))[:20]}


def _hrefs(html: str) -> list[str]:
    import re

    return re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.I)
