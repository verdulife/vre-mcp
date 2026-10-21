"""Search adapter interface.

One adapter per source. A source can be disabled from configuration without breaking the
rest of the system: an unavailable adapter reports an error and the run continues.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ..models import RawSearchResult


@dataclass
class AdapterResult:
    results: list[RawSearchResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    provider: str | None = None


@runtime_checkable
class SearchAdapter(Protocol):
    name: str

    async def search(self, queries: list[str], per_query_limit: int) -> AdapterResult:
        """Run the queries and return raw, traceable results. Never fabricate results."""
