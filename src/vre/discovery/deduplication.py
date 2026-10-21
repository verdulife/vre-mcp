"""Deduplication by normalized page URL and, when available, image identity."""

from __future__ import annotations

from ..models import Candidate
from ..urls import dedupe_key


def dedupe_candidates(candidates: list[Candidate]) -> tuple[list[Candidate], int]:
    """Keep the first occurrence of each page URL and each image URL.

    Returns (kept, removed_count).
    """
    kept: list[Candidate] = []
    seen_pages: set[str] = set()
    seen_images: set[str] = set()
    removed = 0
    for candidate in candidates:
        page_key = dedupe_key(candidate.page_url)
        if page_key in seen_pages:
            removed += 1
            continue
        image_key = dedupe_key(candidate.image.url) if candidate.image and candidate.image.url else None
        if image_key and image_key in seen_images:
            removed += 1
            continue
        seen_pages.add(page_key)
        if image_key:
            seen_images.add(image_key)
        kept.append(candidate)
    return kept, removed
