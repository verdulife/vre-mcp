"""Turn a design brief into specific search queries.

Deliberately small and transparent: no model call, no hidden rewriting. The agent supplies
its own queries when it knows better, and this module only fills the gap.
"""

from __future__ import annotations

import re

MAX_QUERY_TERMS = 14
GENERIC_TERMS = {
    "reference",
    "references",
    "referencia",
    "referencias",
    "inspiration",
    "inspiración",
    "design",
    "diseño",
    "ideas",
}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def build_queries(
    brief: str,
    visual_attributes: list[str] | None = None,
    exclude: list[str] | None = None,
) -> list[str]:
    """Build one primary query plus at most one complementary attribute query."""
    base = _clean(brief)
    attributes = [_clean(item) for item in (visual_attributes or []) if _clean(item)]
    if not base and not attributes:
        return []

    primary_terms = [term for term in base.split(" ") if term]
    if len(primary_terms) > MAX_QUERY_TERMS:
        primary_terms = primary_terms[:MAX_QUERY_TERMS]
    primary = _clean(" ".join(primary_terms))

    lowered = primary.lower()
    for term in exclude or []:
        cleaned = _clean(term)
        if cleaned and cleaned.lower() in lowered:
            primary = re.sub(re.escape(cleaned), "", primary, flags=re.IGNORECASE)
            primary = _clean(primary)

    queries = [primary] if primary else []
    if attributes:
        joined = " ".join(attributes[:4])
        combined = _clean(f"{primary} {joined}")
        if combined and combined.lower() not in {query.lower() for query in queries}:
            queries.append(combined)
    return [query for query in queries if query and query.lower() not in GENERIC_TERMS][:2]
