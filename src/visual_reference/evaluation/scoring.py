"""Transparent, metadata-only scoring.

This module never claims to have looked at an image. It uses what the source actually
declares: title, snippet, URL, verified image dimensions and how the image was discovered.
Every score carries the evidence that produced it, so the agent can disagree in public.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..config import SelectionWeights
from ..models import Candidate

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "about", "over", "under",
    "para", "con", "como", "sobre", "desde", "este", "esta", "unos", "unas", "del", "los",
    "las", "que", "por", "una", "uno", "más", "mas", "sin", "sus", "les",
}

SOCIAL_CARD_DISCOVERY = {"og:image", "twitter:image", "link:image_src"}


@dataclass
class Score:
    relevance: float
    visual_quality: float
    usefulness: float
    novelty: float = 0.0
    overall: float = 0.0
    evidence: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "relevance": round(self.relevance, 2),
            "visual_quality": round(self.visual_quality, 2),
            "usefulness": round(self.usefulness, 2),
            "novelty": round(self.novelty, 2),
            "overall": round(self.overall, 2),
            "evidence": self.evidence,
            "limitations": self.limitations,
        }


def tokenize(text: str) -> set[str]:
    tokens = {token for token in re.findall(r"[a-z0-9áéíóúñü]{3,}", (text or "").lower())}
    return tokens - STOPWORDS


def _clamp(value: float, low: float = 0.0, high: float = 5.0) -> float:
    return max(low, min(high, value))


def score_relevance(candidate: Candidate, brief_terms: set[str], attribute_terms: set[str]) -> tuple[float, list[str]]:
    haystack = tokenize(f"{candidate.title} {candidate.snippet} {candidate.page_url}")
    brief_hits = brief_terms & haystack
    attribute_hits = attribute_terms & haystack
    evidence: list[str] = []
    if brief_hits:
        evidence.append("Brief terms present in title/snippet: " + ", ".join(sorted(brief_hits)[:8]))
    if attribute_hits:
        evidence.append("Requested attributes present: " + ", ".join(sorted(attribute_hits)[:8]))
    if not brief_terms:
        return (2.5, ["No brief terms were available to compare; relevance is unassessed."])
    base = 5.0 * (len(brief_hits) / max(1, min(len(brief_terms), 6))) * 0.6
    base += 5.0 * (len(attribute_hits) / max(1, len(attribute_terms))) * 0.4 if attribute_terms else 0.0
    return _clamp(base), evidence


def image_role(candidate: Candidate) -> str:
    if candidate.image is None:
        return "none"
    if candidate.image.discovery in SOCIAL_CARD_DISCOVERY:
        return "social_card"
    if candidate.image.discovery == "json-ld":
        return "structured_data"
    return "page_image"


def score_image_quality(candidate: Candidate) -> tuple[float, list[str], list[str]]:
    evidence: list[str] = []
    limitations: list[str] = []
    image = candidate.image
    if image is None or not image.verified:
        return (
            0.5,
            ["No verified image bytes for this candidate."],
            ["No verified image for this candidate, so visual quality cannot be assessed."],
        )
    area = (image.width or 0) * (image.height or 0)
    if area >= 1_000_000:
        score = 5.0
    elif area >= 400_000:
        score = 4.2
    elif area >= 150_000:
        score = 3.4
    elif area >= 40_000:
        score = 2.4
    else:
        score = 1.5
    evidence.append(f"Verified image {image.width}×{image.height} ({image.content_type or 'unknown type'}).")
    if image.aspect_ratio is not None:
        if image.aspect_ratio > 3.0 or image.aspect_ratio < 0.2:
            score -= 1.0
            limitations.append(f"Extreme aspect ratio ({image.aspect_ratio}); may be a banner or strip.")
    if image.dominant_colors:
        evidence.append("Dominant colours measured: " + ", ".join(image.dominant_colors))
    return _clamp(score), evidence, limitations


def score_usefulness(candidate: Candidate) -> tuple[float, list[str], list[str]]:
    evidence: list[str] = []
    limitations: list[str] = []
    role = image_role(candidate)
    if role == "structured_data":
        score = 4.6
        evidence.append("Image declared in structured data, likely the work itself.")
    elif role == "page_image":
        score = 4.2
        evidence.append("Image taken from the page body, likely the work itself.")
    elif role == "social_card":
        score = 3.0
        evidence.append(
            "Image is the page's social card (Open Graph/Twitter): it may be a presentation card, "
            "a crop, or include the site's own branding rather than the artwork."
        )
        limitations.append("This image is the page's social card and can differ from the original piece.")
    else:
        score = 0.8
        limitations.append("No image to reuse as a visual reference.")

    if candidate.creator:
        score += 0.3
        evidence.append(f"Creator declared by the page: {candidate.creator}.")
    else:
        limitations.append("No verifiable creator in the metadata; do not assume authorship.")

    if candidate.metadata_confidence == "low":
        score -= 0.4
    return _clamp(score), evidence, limitations


def score_candidate(
    candidate: Candidate,
    *,
    brief: str,
    attributes: list[str] | None = None,
    weights: SelectionWeights | None = None,
) -> Score:
    weights = (weights or SelectionWeights()).normalized()
    brief_terms = tokenize(brief) | tokenize(candidate.query)
    attribute_terms = set()
    for attribute in attributes or []:
        attribute_terms |= tokenize(attribute)

    relevance, relevance_evidence = score_relevance(candidate, brief_terms, attribute_terms)
    quality, quality_evidence, quality_limits = score_image_quality(candidate)
    usefulness, usefulness_evidence, usefulness_limits = score_usefulness(candidate)

    # Novelty is a property of the chosen set, not of one candidate: it stays 0 here and is
    # filled in by the diversity selector.
    weight_sum = weights.relevance + weights.visual_quality + weights.usefulness
    overall = (
        relevance * weights.relevance
        + quality * weights.visual_quality
        + usefulness * weights.usefulness
    ) / (weight_sum or 1)

    limitations = quality_limits + usefulness_limits + [
        "No visual analysis was performed by this server: scores use source metadata and verified image "
        "dimensions only."
    ]
    return Score(
        relevance=relevance,
        visual_quality=quality,
        usefulness=usefulness,
        overall=overall,
        evidence=relevance_evidence + quality_evidence + usefulness_evidence,
        limitations=limitations,
    )


def evaluation_record(candidate: Candidate, score: Score, method: str = "heuristic_v1") -> dict:
    return {
        "candidate_id": candidate.candidate_id,
        "method": method,
        "analysis_origin": "metadata_heuristics",
        "scores": score.as_dict(),
        "image_role": image_role(candidate),
        "candidate": candidate.compact(),
    }
