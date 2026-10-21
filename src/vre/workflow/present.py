"""Build the set the agent presents to the user.

Every field is either a verifiable fact from the source, a measured property of the image
file, or a heuristic labelled as such. Aesthetic interpretation is the agent's job, not this
module's, and the payload says so.
"""

from __future__ import annotations

from ..config import SelectionWeights
from ..evaluation.diversity import DiversePick, select_diverse
from ..evaluation.scoring import Score, image_role, score_candidate
from ..models import Candidate
from .sessions import SearchSession

METHOD = "heuristic_mmr_v1"

# An image below these floors cannot be judged visually, so it never enters a presentation.
MIN_PRESENT_AREA = 120_000
MIN_PRESENT_EDGE = 240


def evaluate_session(
    session: SearchSession,
    weights: SelectionWeights | None = None,
) -> list[tuple[Candidate, Score]]:
    return _score_candidates(
        session.usable(), brief=session.brief, attributes=session.attributes, weights=weights
    )


def _score_candidates(
    candidates: list[Candidate],
    *,
    brief: str,
    attributes: list[str],
    weights: SelectionWeights | None,
) -> list[tuple[Candidate, Score]]:
    scored: list[tuple[Candidate, Score]] = []
    for candidate in candidates:
        score = score_candidate(candidate, brief=brief, attributes=attributes, weights=weights)
        scored.append((candidate, score))
    scored.sort(key=lambda item: item[1].overall, reverse=True)
    return scored


def _meets_size_floor(candidate: Candidate) -> bool:
    """True only when a measured image is large enough to say anything about it."""
    image = candidate.image
    if image is None or not image.width or not image.height:
        return False
    return image.width * image.height >= MIN_PRESENT_AREA and min(image.width, image.height) >= MIN_PRESENT_EDGE


def _pool_and_excluded(session: SearchSession) -> tuple[list[Candidate], int]:
    usable = session.usable()
    pool = [candidate for candidate in usable if _meets_size_floor(candidate)]
    return pool, len(usable) - len(pool)


def _too_small_note(count: int) -> str:
    return (
        f"{count} candidate(s) were left out because the verified image is too small to judge "
        f"(short edge < {MIN_PRESENT_EDGE} px or area < {MIN_PRESENT_AREA} px)."
    )


def _measured_observations(candidate: Candidate) -> list[str]:
    image = candidate.image
    observations: list[str] = []
    if image is None:
        return ["No image available to observe."]
    if image.width and image.height:
        orientation = "horizontal" if image.width > image.height else "vertical" if image.height > image.width else "square"
        observations.append(
            f"Measured image: {image.width}×{image.height} ({orientation}), {image.aspect_ratio}:1."
        )
    if image.dominant_colors:
        observations.append("Dominant colours: " + ", ".join(image.dominant_colors) + ".")
    if image.brightness is not None:
        tone = "dark" if image.brightness < 0.35 else "light" if image.brightness > 0.65 else "mid-tone"
        observations.append(f"Mean brightness {image.brightness} ({tone}).")
    return observations


def _cautions(candidate: Candidate, score: Score) -> list[str]:
    cautions: list[str] = []
    role = image_role(candidate)
    if role == "social_card":
        cautions.append(
            "The image is the page's social card, so it may be a presentation card or a crop rather than the original piece."
        )
    if not candidate.creator:
        cautions.append("No verifiable creator in the metadata; do not attribute authorship.")
    cautions.extend(score.limitations)
    return list(dict.fromkeys(cautions))


def _escape_cell(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def _table_rows(items: list[dict]) -> list[dict]:
    """Ready-to-present rows: clickable image link, short description, valuation.

    The description and the valuation are seeds built from verified facts; the agent replaces
    them with what it actually saw and labels that as its own observation.
    """
    rows: list[dict] = []
    for index, item in enumerate(items, start=1):
        seed_parts = [item["title"]]
        if item.get("image_role") == "social_card":
            seed_parts.append("(page social card)")
        observations = item.get("measured_observations") or []
        if observations:
            seed_parts.append(observations[0])
        rows.append(
            {
                "n": index,
                "image_link": f"[Ver imagen]({item['image_url']})",
                "image_url": item["image_url"],
                "page_link": f"[{_escape_cell(item['title'])}]({item['page_url']})",
                "description": _escape_cell(". ".join(part for part in seed_parts if part)),
                "valuation": f"{item['scores']['overall']:.1f}/5",
                "valuation_basis": "metadata",
                "candidate_id": item["candidate_id"],
            }
        )
    return rows


def _table_markdown(rows: list[dict]) -> str:
    lines = ["| Imagen | Descripción | Valoración |", "| --- | --- | --- |"]
    for row in rows:
        lines.append(f"| {row['image_link']} | {row['description']} | {row['valuation']} |")
    return "\n".join(lines)


def build_presentation(
    session: SearchSession,
    picks: list[DiversePick],
    *,
    requested_limit: int,
    present_min: int,
    present_max: int,
    notes: list[str] | None = None,
    usable_count: int | None = None,
) -> dict:
    notes = list(notes or [])
    items = []
    for pick in picks:
        candidate = pick.candidate
        score = pick.score
        image = candidate.image
        items.append(
            {
                "candidate_id": candidate.candidate_id,
                "title": candidate.title,
                "source": candidate.source,
                "page_url": candidate.page_url,
                "image_url": candidate.image_url,
                "image_verified": bool(image and image.verified),
                "image_mime": image.content_type if image else None,
                "creator": candidate.creator,
                "image_role": image_role(candidate),
                "metadata_confidence": candidate.metadata_confidence,
                "scores": score.as_dict(),
                "why_selected": pick.reasons + score.evidence[:3],
                "measured_observations": _measured_observations(candidate),
                "distance_to_selected": pick.distance_to_selected,
                "cautions": _cautions(candidate, score),
                "verify_visually": f"fetch_reference_image(candidate_id='{candidate.candidate_id}')",
            }
        )

    usable = len(session.usable()) if usable_count is None else usable_count
    if usable < present_min:
        notes.append(
            f"Only {usable} usable reference(s) were verified; the minimum for a diverse set is "
            f"{present_min}. Present what exists and explain the limit instead of inventing more."
        )
    if len(items) < requested_limit:
        notes.append(
            f"The remaining candidates repeated an existing visual direction, so the set stopped at "
            f"{len(items)} instead of filling {requested_limit}."
        )

    table_rows = _table_rows(items)
    return {
        "search_id": session.search_id,
        "brief": session.brief,
        "queries": session.queries,
        "method": METHOD,
        "presentation_format": (
            "Always answer with a Markdown table with exactly these columns: Imagen | Descripción | "
            "Valoración. First column: a clickable `Ver imagen` link to the image URL (no embedded "
            "image needed). Description: one or two lines, the piece and what it contributes, with the "
            "page title linked. Valuation: n/5 plus one short reason; label your own visual observation "
            "as yours and keep it out of the metadata claim."
        ),
        "presentation_table": table_rows,
        "table_markdown": _table_markdown(table_rows),
        "selection_rule": (
            "Greedy MMR-style ranking: 70% metadata score, 30% measured distance to the closest already "
            "chosen image. Distances below 0.12 are treated as the same direction."
        ),
        "presentation": items,
        "count": len(items),
        "present_range": [present_min, present_max],
        "pairwise_distance": [
            {"left": left.candidate.candidate_id, "right": right.candidate.candidate_id,
             "distance": round(_distance_value(left, right), 3)}
            for index, left in enumerate(picks)
            for right in picks[index + 1 :]
        ],
        "notes": notes,
        "agent_instructions": [
            "Call fetch_reference_image for every item you intend to describe: these payloads were not visually inspected.",
            "Present image, title, source link, one concrete contribution, one visual decision to research, and any caution.",
            "Then ask whether to choose, refine, or explore another direction; do not start the final design unasked.",
        ],
    }


def _distance_value(left: DiversePick, right: DiversePick) -> float:
    from ..evaluation.diversity import distance

    return distance(left.candidate, right.candidate)


def present_session(
    session: SearchSession,
    *,
    limit: int | None,
    weights: SelectionWeights | None,
    present_min: int,
    present_max: int,
    lambda_relevance: float = 0.7,
) -> dict:
    pool, excluded = _pool_and_excluded(session)
    notes = [_too_small_note(excluded)] if excluded else []
    scored = _score_candidates(
        pool, brief=session.brief, attributes=session.attributes, weights=weights
    )
    if not scored:
        reason = (
            "No candidate with a large enough verified image survived, so there is nothing to present."
            if excluded
            else "No candidate survived verification, so there is nothing to present."
        )
        return {
            "search_id": session.search_id,
            "brief": session.brief,
            "presentation": [],
            "count": 0,
            "notes": notes + [reason],
        }
    requested = limit or present_max
    requested = max(1, min(requested, present_max))
    picks = select_diverse(scored, requested, lambda_relevance=lambda_relevance)
    payload = build_presentation(
        session,
        picks,
        requested_limit=requested,
        present_min=present_min,
        present_max=present_max,
        notes=notes,
        usable_count=len(pool),
    )
    session.shown.extend(pick.candidate.candidate_id for pick in picks if pick.candidate.candidate_id not in session.shown)
    return payload
