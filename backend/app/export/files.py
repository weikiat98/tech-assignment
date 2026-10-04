"""Export formats: JSON, CSV (facts + cleaned data) and PDF via Gotenberg (headless Chromium)."""

from __future__ import annotations

import csv
import html
import io
import json
import zipfile
from typing import Any

import httpx
import markdown as md_lib

from app.config import get_settings


def to_json(result: dict[str, Any]) -> bytes:
    return json.dumps(result, indent=2, ensure_ascii=False).encode()


def to_csv_zip(result: dict[str, Any], frames: dict[str, Any] | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        facts = io.StringIO()
        writer = csv.writer(facts)
        writer.writerow(["id", "label", "value", "unit", "display", "method", "source_keys"])
        for f in result.get("facts", []):
            writer.writerow([f["id"], f["label"], f["value"], f["unit"], f["display"], f["method"],
                             ";".join(f["source_keys"])])
        zf.writestr("facts.csv", facts.getvalue())
        for key, frame in (frames or {}).items():
            zf.writestr(f"data_{key.replace(':', '_')}.csv", frame.to_csv(index=False))
        zf.writestr("datasets.json", json.dumps(result.get("datasets", []), indent=2))
    return buf.getvalue()


def to_html(result: dict[str, Any]) -> str:
    body = md_lib.markdown(result.get("markdown") or "", extensions=["tables"])
    charts = result.get("charts", [])
    divs = "\n".join(f'<h3>{html.escape(c["title"])}</h3><div id="chart{i}" class="chart"></div>'
                     for i, c in enumerate(charts))
    scripts = "\n".join(
        f"Plotly.newPlot('chart{i}', {json.dumps(c['spec']['data'])}, "
        f"Object.assign({json.dumps(c['spec']['layout'])}, {{width: 720, height: 380}}), {{staticPlot: true}});"
        for i, c in enumerate(charts))
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Report</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>body{{font-family:Helvetica,Arial,sans-serif;max-width:760px;margin:24px auto;color:#1f2937;font-size:12px}}
h1{{font-size:20px}}h2{{font-size:15px;border-bottom:1px solid #e5e7eb;padding-bottom:4px}}
table{{border-collapse:collapse;width:100%;font-size:10px}}td,th{{border:1px solid #e5e7eb;padding:3px}}
.chart{{page-break-inside:avoid}}</style></head><body>{body}<h2>Charts</h2>{divs}
<script>{scripts}</script></body></html>"""


async def to_pdf(result: dict[str, Any]) -> bytes:
    """Render the HTML report (with live Plotly charts) to PDF using Gotenberg's Chromium route."""
    files = {"files": ("index.html", to_html(result).encode(), "text/html")}
    data = {"waitDelay": "2s", "printBackground": "true", "marginTop": "0.5", "marginBottom": "0.5"}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{get_settings().gotenberg_url}/forms/chromium/convert/html", files=files, data=data)
        resp.raise_for_status()
        return resp.content
