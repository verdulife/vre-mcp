"""Data shapes shared by discovery, evaluation, storage and the MCP layer."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class RawSearchResult:
    """A search result before any page or image work."""

    title: str
    page_url: str
    snippet: str = ""
    query: str = ""
    source: str = "pi_web_access"


@dataclass
class ImageInfo:
    """A validated image resource attached to a candidate."""

    url: str
    width: int | None = None
    height: int | None = None
    content_type: str | None = None
    byte_size: int | None = None
    discovery: str = "og:image"  # og:image | twitter:image | link:image_src | json-ld | img
    verified: bool = False
    dominant_colors: list[str] = field(default_factory=list)
    brightness: float | None = None
    aspect_ratio: float | None = None


@dataclass
class Candidate:
    candidate_id: str
    title: str
    page_url: str
    source: str
    query: str = ""
    snippet: str = ""
    image: ImageInfo | None = None
    creator: str | None = None
    metadata_confidence: str = "low"  # high | medium | low
    status: str = "ok"  # ok | excluded
    exclusion_reason: str | None = None
    retrieved_at: str = field(default_factory=utc_now)

    @property
    def image_url(self) -> str | None:
        return self.image.url if self.image else None

    def compact(self) -> dict[str, Any]:
        image = self.image
        data = {
            "candidate_id": self.candidate_id,
            "title": self.title,
            "source": self.source,
            "page_url": self.page_url,
            "image_url": self.image_url,
            "image_verified": bool(image and image.verified),
            "image_mime": image.content_type if image else None,
            "creator": self.creator,
            "metadata_confidence": self.metadata_confidence,
            "status": self.status,
            "retrieved_at": self.retrieved_at,
        }
        if image and image.verified:
            data["image_dimensions"] = [image.width, image.height]
        if self.snippet:
            data["snippet"] = self.snippet
        if self.exclusion_reason:
            data["exclusion_reason"] = self.exclusion_reason
        return data

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["image_url"] = self.image_url
        return data


@dataclass
class SearchOutcome:
    brief: str
    queries: list[str]
    candidates: list[Candidate]
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    session_id: str | None = None
    inspected_visually: bool = False

    def compact(self, include_snippet: bool = True) -> dict[str, Any]:
        candidates = []
        for candidate in self.candidates:
            data = candidate.compact()
            if not include_snippet:
                data.pop("snippet", None)
            candidates.append(data)
        payload: dict[str, Any] = {
            "brief": self.brief,
            "queries": self.queries,
            "candidates": candidates,
            "warnings": self.warnings,
            "errors": self.errors,
            "vision": {
                "enabled": self.inspected_visually,
                "note": (
                    "Candidates were produced from search metadata and page images. No image was "
                    "inspected by this server; visual judgement belongs to the agent."
                ),
            },
        }
        if self.session_id:
            payload["session_id"] = self.session_id
        return payload
