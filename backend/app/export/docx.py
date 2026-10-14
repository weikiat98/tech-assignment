"""Word (.docx) export, built from the same structured result as the Markdown export.

Every sentence and number comes from the result JSON, so the .docx cannot disagree with the Markdown
(tests/unit/test_docx_export.py compares them). Charts are not embedded: the PDF path renders them in a
browser, and there is no static image renderer here.
"""

from __future__ import annotations

import io
from typing import Any

from docx import Document
from docx.shared import Pt

SECTIONS = (("Key findings", "key_findings"), ("Sector analysis", "sector_analysis"),
            ("Policy implications", "policy_implications"))


def _claims(doc, claims: list[dict[str, Any]]) -> None:
    for c in claims:
        cites = " ".join(f"[{f}]" for f in c.get("fact_ids", []))
        doc.add_paragraph(f"{c['text']} {cites}".rstrip(), style="List Bullet")


def to_docx(result: dict[str, Any]) -> bytes:
    report = result.get("report") or {}
    verification = result.get("verification") or {}
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(11)
    doc.add_heading(report.get("title", "Analysis report"), level=0)
    doc.add_paragraph(f"Query: {result.get('query', '')}")
    status = "passed" if verification.get("passed") else "issues found"
    doc.add_paragraph(f"Verification: {status} (numeric {verification.get('numeric_pass_rate', 0):.0%}, "
                      f"citations {verification.get('citation_pass_rate', 0):.0%}, "
                      f"entities {verification.get('entity_pass_rate', 0):.0%})")
    doc.add_heading("Executive summary", level=1)
    doc.add_paragraph(report.get("executive_summary", ""))
    for title, key in SECTIONS:
        if report.get(key):
            doc.add_heading(title, level=1)
            _claims(doc, report[key])
    notes = result.get("context_notes") or []
    if notes:
        doc.add_heading("Context from the web", level=1)
        for n in notes:
            flag = " (suspected prompt-injection text removed)" if n.get("injection_flagged") else ""
            doc.add_paragraph(f"Reported by {n['title']} ({n['url']}, trust tier {n['trust_tier']}){flag}: "
                              f"\"{n['excerpt'][:300]}\"", style="List Bullet")
    if report.get("limitations"):
        doc.add_heading("Limitations", level=1)
        for item in report["limitations"]:
            doc.add_paragraph(item, style="List Bullet")
    doc.add_heading("Facts", level=1)
    table = doc.add_table(rows=1, cols=5)
    table.style = "Light Grid Accent 1"
    for cell, head in zip(table.rows[0].cells, ("Id", "Fact", "Value", "Method", "Sources"), strict=True):
        cell.text = head
    for f in result.get("facts", []):
        row = table.add_row().cells
        for cell, text in zip(row, (f["id"], f["label"], f["display"], f["method"], ", ".join(f["source_keys"])),
                              strict=True):
            cell.text = str(text)
    doc.add_heading("Data sources", level=1)
    for d in result.get("datasets", []):
        fallback = f" - fallback: {d['fallback_reason']}" if d.get("is_fallback") else ""
        agency = f", {d['agency']}" if d.get("agency") else ""
        quality = (d.get("quality") or {}).get("score") or 0
        doc.add_paragraph(f"{d['key']} - {d['title']}{agency}. {d.get('url') or ''} "
                          f"(retrieved {d['retrieved_at'][:10]}, quality {quality:.2f}){fallback}",
                          style="List Bullet")
    note = doc.add_paragraph("Derived values (growth rates, shares, correlations, projections) are computed by "
                             "this platform from the cited tables and are not attributed to the source agencies.")
    note.runs[0].italic = True
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
