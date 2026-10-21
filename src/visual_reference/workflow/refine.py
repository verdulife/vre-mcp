"""Refinement planning: keep the briefing, change one dimension.

Modes:
  same    - more references close to what was already chosen
  narrow  - tighten an attribute or constraint
  explore - deliberately different direction

The plan is heuristic and visible: the generated queries are returned so the agent can see
and correct them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..workflow.sessions import SearchSession

MODES = ("same", "narrow", "explore")


@dataclass
class RefinementPlan:
    mode: str
    queries: list[str]
    exclude: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"mode": self.mode, "queries": self.queries, "exclude": self.exclude, "notes": self.notes}


def _instruction_terms(instruction: str, limit: int = 8) -> list[str]:
    terms = re.findall(r"[a-zA-Z0-9À-ÿ]{3,}", instruction or "")
    seen: list[str] = []
    for term in terms:
        lowered = term.lower()
        if lowered in seen:
            continue
        # keep the instruction's own words, minus stopwords, in order
        if lowered in {
            "the", "and", "for", "with", "that", "this", "from", "into", "about", "more", "less",
            "mas", "menos", "pero", "como", "quiero", "busca", "buscar", "hacia", "direccion",
        }:
            continue
        seen.append(lowered)
        if len(seen) >= limit:
            break
    return seen


def plan_refinement(session: SearchSession, mode: str, instruction: str) -> RefinementPlan:
    mode = (mode or "").strip().lower()
    if mode not in MODES:
        raise ValueError(f"Unknown refinement mode {mode!r}; use one of {', '.join(MODES)}.")
    text = (instruction or "").strip()
    if not text:
        raise ValueError("A refinement instruction is required.")
    terms = _instruction_terms(text)
    notes: list[str] = []
    base = session.queries[0] if session.queries else session.brief

    if mode == "same":
        queries = [f"{base} {text}" if text not in base else base]
        notes.append("Kept the original query and added the instruction to stay close to the chosen direction.")
    elif mode == "narrow":
        brief_words = " ".join(session.brief.split()[:10])
        queries = [" ".join(part for part in (brief_words, " ".join(terms)) if part)]
        notes.append("Kept the briefing and tightened it with the requested attribute.")
    else:  # explore
        queries = [" ".join(terms) or text]
        notes.append("Dropped the original query on purpose to look for a deliberately different direction.")

    queries = [query.strip() for query in queries if query.strip()]
    return RefinementPlan(mode=mode, queries=queries[:2], exclude=list(session.exclude), notes=notes)


def previous_pages(session: SearchSession) -> set[str]:
    return {candidate.page_url for candidate in session.outcome.candidates}
