"""Discovery orchestration: query, search, fetch pages, validate images.

This is the honest core of the engine: a candidate reaches the agent only after its page was
actually fetched and its image actually decoded, or it is labelled with the reason why not.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field

import httpx

from ..config import Config
from ..http_safety import FetchError, fetch_html
from ..models import Candidate, ImageInfo, SearchOutcome
from ..sources import build_adapters
from ..urls import dedupe_key, normalize_url
from .deduplication import dedupe_candidates
from .image_extract import extract_image_candidates
from .image_probe import probe_image
from .query_builder import build_queries

MAX_PAGE_WORKERS = 4
MAX_IMAGE_ATTEMPTS = 3
MIN_IMAGE_EDGE = 160
MAX_REPORTED_WARNINGS = 6

# Site chrome is never a design reference. Rejecting it here avoids paying to decode it.
# A noise word only counts as chrome when it names the file itself (logo.png,
# placeholder-image.jpg), never when it is merely the start of a real file name
# (uploads/logo-experiment-poster.jpg is a poster).
NOISE_URL_RE = re.compile(
    r"(?:/|_|-)(logo|favicon|sprite|placeholder|avatar|watermark|spinner|pixel|blank|transparent)"
    r"(?:[_-](?:image|img|icon|sprite|small|thumb|thumbnail))?"
    r"(?:[_-]?\d+x)?"
    r"\.(?:gif|png|jpe?g|webp|svg|ico|bmp|avif)"
    r"|1x1\.(?:gif|png)|spacer\.(?:gif|png)",
    re.IGNORECASE,
)


@dataclass
class DiscoveryRequest:
    brief: str
    queries: list[str] = field(default_factory=list)
    visual_attributes: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    limit: int | None = None
    sources: list[str] | None = None


def candidate_id_for(page_url: str) -> str:
    import hashlib

    return "cand_" + hashlib.sha1(dedupe_key(page_url).encode("utf-8")).hexdigest()[:12]


def _excluded(candidate: Candidate, terms: list[str]) -> str | None:
    haystack = f"{candidate.title} {candidate.snippet} {candidate.page_url}".lower()
    for term in terms:
        cleaned = (term or "").strip().lower()
        if cleaned and cleaned in haystack:
            return cleaned
    return None


async def _resolve_images(
    client: httpx.AsyncClient,
    config: Config,
    page_url: str,
) -> tuple[ImageInfo | None, str | None]:
    """Fetch one page and return the best verified image plus an optional failure note."""
    try:
        html = await fetch_html(page_url, config.http, client=client)
    except FetchError as exc:
        return None, str(exc)
    except Exception as exc:  # defensive: one page must never break the run
        return None, f"Failed to read {page_url}: {type(exc).__name__}"

    references = extract_image_candidates(html, page_url)
    references = [reference for reference in references if not NOISE_URL_RE.search(reference.url)]
    if not references:
        return None, f"No usable image declared by the page {page_url}"

    best: ImageInfo | None = None
    last_error: str | None = None
    for reference in references[:MAX_IMAGE_ATTEMPTS]:
        try:
            info = await probe_image(
                reference.url,
                config.http,
                max_bytes=config.vision.max_image_bytes,
                client=client,
                discovery=reference.discovery,
            )
        except FetchError as exc:
            last_error = str(exc)
            continue
        except Exception as exc:
            last_error = f"Failed to read image {reference.url}: {type(exc).__name__}"
            continue
        if (info.width or 0) < MIN_IMAGE_EDGE and (info.height or 0) < MIN_IMAGE_EDGE:
            last_error = f"Image {info.url} is too small to be a usable reference"
            continue
        area = (info.width or 0) * (info.height or 0)
        if best is None or area > (best.width or 0) * (best.height or 0):
            best = info
    return best, (None if best else last_error or f"No usable image found on {page_url}")


async def discover_references(config: Config, request: DiscoveryRequest) -> SearchOutcome:
    queries = [query.strip() for query in request.queries if query.strip()] or build_queries(
        request.brief, request.visual_attributes, request.exclude
    )
    outcome = SearchOutcome(brief=request.brief, queries=queries, candidates=[])

    if not queries:
        outcome.errors.append("A brief or at least one query is required to search.")
        return outcome

    adapters = build_adapters(config)
    if request.sources:
        wanted = {name.strip() for name in request.sources if name.strip()}
        adapters = [adapter for adapter in adapters if adapter.name in wanted]

    raw = []
    for adapter in adapters:
        result = await adapter.search(queries, config.search.per_query_limit)
        raw.extend(result.results)
        outcome.warnings.extend(result.warnings)
        outcome.errors.extend(result.errors)
        if result.provider:
            outcome.warnings.append(f"Search provider used by {adapter.name}: {result.provider}")

    limit = min(
        request.limit or config.search.candidate_limit,
        config.search.candidate_limit,
    )

    candidates: list[Candidate] = []
    seen: set[str] = set()
    for item in raw:
        key = dedupe_key(item.page_url)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            Candidate(
                candidate_id=candidate_id_for(item.page_url),
                title=item.title,
                page_url=normalize_url(item.page_url),
                source=item.source,
                query=item.query,
                snippet=item.snippet,
            )
        )
        if len(candidates) >= config.search.candidate_limit:
            break

    filtered: list[Candidate] = []
    for candidate in candidates:
        term = _excluded(candidate, request.exclude)
        if term:
            candidate.status = "excluded"
            candidate.exclusion_reason = f"matches excluded term: {term}"
            continue
        filtered.append(candidate)

    if not raw:
        return outcome

    work = filtered[: max(config.search.page_fetch_limit, limit)]
    semaphore = asyncio.Semaphore(MAX_PAGE_WORKERS)
    async with httpx.AsyncClient(
        follow_redirects=False,
        timeout=httpx.Timeout(config.http.timeout_seconds),
        headers={"User-Agent": config.http.user_agent},
    ) as client:

        async def one(candidate: Candidate) -> None:
            async with semaphore:
                image, note = await _resolve_images(client, config, candidate.page_url)
            if image is not None:
                candidate.image = image
                candidate.metadata_confidence = "high" if image.discovery == "og:image" else "medium"
            else:
                candidate.status = "no_image"
                candidate.exclusion_reason = note
                candidate.metadata_confidence = "low"

        await asyncio.gather(*(one(candidate) for candidate in work))

    kept, removed = dedupe_candidates(filtered)
    if removed:
        outcome.warnings.append(f"Removed {removed} duplicate candidate(s) after image resolution.")

    usable = [candidate for candidate in kept if candidate.status == "ok"]
    excluded = [candidate for candidate in kept if candidate.status != "ok"]
    outcome.candidates = (usable + excluded)[:limit]

    without_image = [candidate for candidate in usable if candidate.image is None]
    if without_image:
        outcome.warnings.append(
            f"{len(without_image)} candidate(s) could not be verified with an image."
        )
    outcome.warnings = outcome.warnings[:MAX_REPORTED_WARNINGS] + (
        [f"{len(outcome.warnings) - MAX_REPORTED_WARNINGS} more warning(s) omitted."]
        if len(outcome.warnings) > MAX_REPORTED_WARNINGS
        else []
    )
    outcome.warnings.append(
        "Nothing here was visually inspected by this server: image URLs and dimensions are verified, "
        "visual judgement must come from the agent's own view of the image."
    )
    return outcome


def find_candidate(outcome: SearchOutcome, candidate_id: str) -> Candidate | None:
    for candidate in outcome.candidates:
        if candidate.candidate_id == candidate_id:
            return candidate
    return None
