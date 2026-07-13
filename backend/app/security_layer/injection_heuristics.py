import re

# First-pass, cheap heuristic layer. Catches obvious prompt-injection /
# jailbreak phrasing and raw SQL-injection-style tokens before spending an
# LLM call. Not exhaustive by design -- injection_classifier.py is the
# second, semantic layer that catches paraphrased attempts this misses.
_PATTERNS = [
    re.compile(r"ignore (all |any )?(previous|prior|above) instructions", re.I),
    re.compile(r"disregard (all |any )?(previous|prior|above)", re.I),
    re.compile(r"you are now", re.I),
    re.compile(r"system prompt", re.I),
    re.compile(r"reveal (your|the) (instructions|prompt|system message)", re.I),
    re.compile(r"act as (a |an )?(?!.*client)", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"\bDROP\s+TABLE\b", re.I),
    re.compile(r"\bUNION\s+SELECT\b", re.I),
    re.compile(r";\s*--"),
    re.compile(r"\bOR\s+1\s*=\s*1\b", re.I),
    re.compile(r"<\s*script", re.I),
]


def scan_for_injection(text: str) -> list[str]:
    """Returns the list of matched pattern descriptions (empty if clean)."""
    return [p.pattern for p in _PATTERNS if p.search(text)]
