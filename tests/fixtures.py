"""Shared fixtures for the test suite. No network access, no real search."""

from __future__ import annotations

from visual_reference.models import Candidate, ImageInfo


def make_candidate(
    candidate_id: str,
    page_url: str | None = None,
    *,
    width: int = 1200,
    height: int = 800,
    colors: tuple[str, ...] = ("#111111", "#dd2222"),
    brightness: float = 0.3,
    discovery: str = "og:image",
    status: str = "ok",
    title: str = "Brutalist festival poster",
    snippet: str = "Bold typographic poster for an electronic music festival",
    query: str = "brutalist festival poster",
    creator: str | None = None,
    with_image: bool = True,
) -> Candidate:
    image = None
    if with_image:
        image = ImageInfo(
            url=f"{page_url or 'https://example.test/page'}-image.jpg",
            width=width,
            height=height,
            content_type="image/jpeg",
            byte_size=120_000,
            discovery=discovery,
            verified=True,
            dominant_colors=list(colors),
            brightness=brightness,
            aspect_ratio=round(width / height, 3),
        )
    return Candidate(
        candidate_id=candidate_id,
        title=title,
        page_url=page_url or f"https://example.test/{candidate_id}",
        source="pi_web_access",
        query=query,
        snippet=snippet,
        image=image,
        creator=creator,
        metadata_confidence="high" if discovery == "og:image" else "medium",
        status=status,
        exclusion_reason=None if status == "ok" else "test fixture",
    )
