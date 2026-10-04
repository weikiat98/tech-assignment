"""Domain trust tiers and prompt-injection heuristics for web content (plan.md §5.4)."""

import re
from urllib.parse import urlparse

TIER1_SUFFIXES = (".gov.sg",)
TIER2_DOMAINS = ("worldbank.org", "ilo.org", "imf.org", "oecd.org", "un.org", "adb.org")

INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) (instructions|prompts)",
    r"disregard (the )?(system|previous) (prompt|instructions)",
    r"you are now",
    r"new instructions:",
    r"system prompt",
    r"reveal (your|the) (prompt|instructions|api key)",
    r"call the tool",
    r"<\s*/?\s*(system|assistant)\s*>",
]
_INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.I)


def trust_tier(url: str) -> int:
    host = (urlparse(url).hostname or "").lower()
    if host.endswith(TIER1_SUFFIXES) or host == "gov.sg":
        return 1
    if any(host == d or host.endswith("." + d) for d in TIER2_DOMAINS):
        return 2
    return 3


def detect_injection(text: str) -> list[str]:
    return sorted({m.group(0) for m in _INJECTION_RE.finditer(text or "")})


def strip_injection(text: str) -> str:
    return _INJECTION_RE.sub("[removed: suspected instruction]", text or "")
