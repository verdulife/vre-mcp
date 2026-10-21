"""Candidate discovery: queries, deduplication, page image extraction."""

from .deduplication import dedupe_candidates
from .orchestrator import DiscoveryRequest, candidate_id_for, discover_references, find_candidate
from .query_builder import build_queries

__all__ = [
    "DiscoveryRequest",
    "build_queries",
    "candidate_id_for",
    "dedupe_candidates",
    "discover_references",
    "find_candidate",
]
