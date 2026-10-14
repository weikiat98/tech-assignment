"""The .docx export carries exactly the numbers and sentences of the Markdown export."""

import io
import re

from docx import Document

from app.export.docx import to_docx
from app.export.markdown import render

RESULT = {
    "query": "Analyse employment in the technology sector, 2020-2024",
    "report": {
        "title": "Technology employment, 2020-2024",
        "executive_summary": "Employment rose from 200.1 thousand in 2020 to 250.4 thousand in 2024.",
        "key_findings": [{"text": "Employment grew 25.1% over the period.", "fact_ids": ["F1", "F2"]}],
        "sector_analysis": [],
        "policy_implications": [{"text": "Training capacity should follow demand.", "fact_ids": ["F2"]}],
        "limitations": ["Internal programme data is synthetic."],
    },
    "verification": {"passed": True, "numeric_pass_rate": 1, "citation_pass_rate": 1, "entity_pass_rate": 1},
    "facts": [{"id": "F1", "label": "Employment 2024", "display": "250.4 thousand", "method": "level",
               "source_keys": ["singstat:M1"]},
              {"id": "F2", "label": "Change", "display": "25.1%", "method": "percent_change",
               "source_keys": ["singstat:M1"]}],
    "datasets": [{"key": "singstat:M1", "title": "Employment by sector", "agency": "SingStat", "url": "https://x.sg",
                  "retrieved_at": "2026-10-14T01:02:03", "quality": {"score": 0.97}, "is_fallback": False}],
    "context_notes": [],
}


def _docx_text(blob: bytes) -> str:
    doc = Document(io.BytesIO(blob))
    cells = [c.text for t in doc.tables for row in t.rows for c in row.cells]
    return "\n".join([p.text for p in doc.paragraphs] + cells)


def test_docx_numbers_match_markdown():
    markdown = render(RESULT)
    text = _docx_text(to_docx(RESULT))
    number = re.compile(r"\d[\d,]*\.?\d*%?")
    for token in set(number.findall(markdown)):
        assert token in text, f"{token} is in the Markdown export but not the .docx"
    for sentence in (RESULT["report"]["executive_summary"], RESULT["report"]["key_findings"][0]["text"],
                     RESULT["report"]["limitations"][0]):
        assert sentence in text
