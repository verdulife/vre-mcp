"""Diversity selection with transparent heuristics (no embeddings).

Candidates are compared on measurable properties of the verified image file: aspect ratio,
mean brightness, dominant colour families and pixel area. Selection is a greedy MMR-style
walk: relevance never disappears, but a near-duplicate of an already chosen direction loses.

This is deliberately coarse. It separates "same idea, different page" from "different idea",
which is the job; it does not pretend to judge aesthetics.
"""

from __future__ import annotations

import colorsys
import math
from dataclasses import dataclass, field
from typing import Iterable

from ..models import Candidate
from .scoring import Score

ASPECT_STEPS = (0.2, 0.5, 0.75, 1.0, 1.33, 1.78, 2.5, 4.0)
BRIGHTNESS_STEPS = 4
METHOD = "heuristic_mmr_v1"


def color_family(hex_color: str) -> str:
    value = (hex_color or "").lstrip("#")
    if len(value) != 6:
        return "unknown"
    try:
        r, g, b = (int(value[index : index + 2], 16) / 255 for index in (0, 2, 4))
    except ValueError:
        return "unknown"
    hue, saturation, brightness = colorsys.rgb_to_hsv(r, g, b)
    hue *= 360
    if brightness < 0.15:
        return "black"
    if brightness > 0.9 and saturation < 0.12:
        return "white"
    if saturation < 0.16:
        return "gray"
    if 15 <= hue < 50 and brightness < 0.55:
        return "brown"
    if hue < 15 or hue >= 345:
        return "red"
    if hue < 45:
        return "orange"
    if hue < 70:
        return "yellow"
    if hue < 165:
        return "green"
    if hue < 200:
        return "cyan"
    if hue < 260:
        return "blue"
    if hue < 300:
        return "purple"
    return "pink"


def feature_vector(candidate: Candidate) -> dict:
    image = candidate.image
    if image is None:
        return {"aspect": None, "brightness": None, "palette": set(), "size_class": None}
    aspect = image.aspect_ratio or (image.width / image.height if image.width and image.height else None)
    aspect_class = None
    if aspect:
        aspect_class = min(range(len(ASPECT_STEPS)), key=lambda index: abs(math.log(aspect / ASPECT_STEPS[index])))
    brightness = image.brightness
    brightness_class = None if brightness is None else min(
        BRIGHTNESS_STEPS - 1, int(brightness * BRIGHTNESS_STEPS)
    )
    palette = {color_family(color) for color in image.dominant_colors if color_family(color) != "unknown"}
    area = (image.width or 0) * (image.height or 0)
    size_class = 0 if area < 150_000 else 1 if area < 600_000 else 2
    return {
        "aspect": aspect_class,
        "brightness": brightness_class,
        "palette": palette,
        "size_class": size_class,
    }


def distance(a: Candidate, b: Candidate) -> float:
    left, right = feature_vector(a), feature_vector(b)
    parts: list[float] = []

    if left["aspect"] is not None and right["aspect"] is not None:
        parts.append(min(1.0, abs(left["aspect"] - right["aspect"]) / 3.0))
    if left["brightness"] is not None and right["brightness"] is not None:
        parts.append(abs(left["brightness"] - right["brightness"]) / (BRIGHTNESS_STEPS - 1))
    if left["palette"] and right["palette"]:
        union = left["palette"] | right["palette"]
        inter = left["palette"] & right["palette"]
        parts.append(1.0 - (len(inter) / len(union) if union else 0.0))
    if left["size_class"] is not None and right["size_class"] is not None:
        parts.append(abs(left["size_class"] - right["size_class"]) / 2.0)

    if not parts:
        return 0.5  # unknown similarity: never claim more than that
    return sum(parts) / len(parts)


@dataclass
class DiversePick:
    candidate: Candidate
    score: Score
    distance_to_selected: float | None = None
    reasons: list[str] = field(default_factory=list)


def select_diverse(
    pool: Iterable[tuple[Candidate, Score]],
    limit: int,
    *,
    lambda_relevance: float = 0.7,
    min_distance: float = 0.12,
) -> list[DiversePick]:
    """Greedy MMR-style selection that reports the distance behind every pick."""
    remaining = [(candidate, score) for candidate, score in pool if candidate.status == "ok"]
    if not remaining:
        return []
    limit = max(1, limit)
    selected: list[DiversePick] = []
    first_candidate, first_score = max(remaining, key=lambda item: item[1].overall)
    remaining = [item for item in remaining if item[0].candidate_id != first_candidate.candidate_id]
    selected.append(
        DiversePick(
            candidate=first_candidate,
            score=first_score,
            distance_to_selected=None,
            reasons=["Highest metadata score in the pool; chosen as the first direction."],
        )
    )

    while remaining and len(selected) < limit:
        best: tuple[tuple[float, float], Candidate, Score, float] | None = None
        for candidate, score in remaining:
            nearest = min(distance(candidate, picked.candidate) for picked in selected)
            mmr = lambda_relevance * (score.overall / 5.0) + (1 - lambda_relevance) * nearest
            candidate_key = (mmr, score.overall)
            if best is None or candidate_key > best[0]:
                best = (candidate_key, candidate, score, nearest)
        assert best is not None
        _key, candidate, score, nearest = best
        if nearest < min_distance and len(selected) >= 2:
            break  # remaining candidates would repeat an existing direction
        reasons = []
        if nearest < 0.2:
            reasons.append("Score is high but it is visually close to an already chosen direction.")
        else:
            reasons.append(f"Adds a direction {nearest:.2f} away from the closest chosen candidate.")
        selected.append(
            DiversePick(
                candidate=candidate,
                score=score,
                distance_to_selected=round(nearest, 3),
                reasons=reasons,
            )
        )
        remaining = [item for item in remaining if item[0].candidate_id != candidate.candidate_id]
    return selected


def pairwise_distances(candidates: list[Candidate]) -> list[dict]:
    distances = []
    for index, left in enumerate(candidates):
        for right in candidates[index + 1 :]:
            distances.append(
                {
                    "left": left.candidate_id,
                    "right": right.candidate_id,
                    "distance": round(distance(left, right), 3),
                }
            )
    return distances
