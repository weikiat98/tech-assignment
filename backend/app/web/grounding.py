"""Deterministic grounding check for values extracted from web pages.

An LLM-extracted number survives only if it literally appears in the fetched page
text (after normalising thousands separators and trailing zeros).
"""

import re

_NUM = re.compile(r"-?\d[\d,]*\.?\d*")


def _norm(token: str) -> str:
    token = token.replace(",", "")
    if "." in token:
        token = token.rstrip("0").rstrip(".")
    return token.lstrip("+")


def numbers_in(text: str) -> set[str]:
    return {_norm(t) for t in _NUM.findall(text or "") if any(ch.isdigit() for ch in t)}


def is_grounded(value: float | str, page_numbers: set[str]) -> bool:
    if isinstance(value, str):
        candidates = {_norm(value)}
    else:
        candidates = {_norm(f"{value}"), _norm(f"{value:.0f}") if float(value).is_integer() else _norm(f"{value}")}
    return bool(candidates & page_numbers)
