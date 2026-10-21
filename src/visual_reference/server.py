"""MCP server entry point.

Tools, in the order the agent should use them:

  engine_status          - what is actually available here
  search_references      - real search, real page images, traceable provenance
  evaluate_references    - transparent metadata scores with evidence and limits
  present_reference_set  - a small set chosen for difference, not ranking
  refine_search          - same / narrow / explore from the same briefing
  fetch_reference_image  - hand a real image to the model as an MCP image block
  save_references        - persist only what the user chose
  get_project_references - compact cards for the active project
  list_projects          - what exists locally
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.fastmcp.utilities.types import Image

from . import __version__
from .config import Config, load_config, resolve_database_path
from .discovery.image_probe import prepare_for_model
from .discovery.orchestrator import DiscoveryRequest, discover_references
from .evaluation.scoring import evaluation_record
from .http_safety import FetchError, fetch_image_bytes
from .models import Candidate, SearchOutcome
from .sources.pi_web_access import PiWebAccessAdapter
from .storage import Database, Repository
from .workflow.present import evaluate_session, present_session
from .workflow.refine import plan_refinement, previous_pages
from .workflow.sessions import SearchSession, SessionStore

MAX_CACHED_CANDIDATES = 500

INSTRUCTIONS = """\
Visual Reference Engine: finds real, traceable visual references for design work.

Rules the agent must keep:
- `search_references` returns candidates with a page URL and a verified image URL. It never
  inspects images itself, so visual judgement must come from your own view of the image.
- Use `fetch_reference_image` to actually see a candidate before describing it visually.
  Never describe an image you have not received.
- Scores from `evaluate_references` come from metadata and measured image properties only.
  Your own visual observation, clearly labelled, outranks them.
- `present_reference_set` selects for difference, not for ranking. Present its cautions where
  they matter: a social card may not be the artwork itself.
- Save only references the user chose or authorized. Do not start the final design unasked.
"""

mcp = FastMCP("visual_reference", instructions=INSTRUCTIONS, log_level="WARNING")

_config: Config | None = None
_repository: Repository | None = None
_candidates: "OrderedDict[str, Candidate]" = OrderedDict()
_sessions = SessionStore()


def get_config() -> Config:
    global _config
    if _config is None:
        _config = load_config()
    return _config


def get_repository() -> Repository:
    global _repository
    if _repository is None:
        _repository = Repository(Database(resolve_database_path(get_config())))
    return _repository


def reset_state() -> None:
    """Testing hook: forget configuration, sessions and cache."""
    global _config, _repository
    _config = None
    if _repository is not None:
        _repository.database.close()
    _repository = None
    _candidates.clear()
    _sessions.clear()


def _json(payload: dict | list) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _remember(outcome: SearchOutcome) -> None:
    for candidate in outcome.candidates:
        _candidates[candidate.candidate_id] = candidate
    while len(_candidates) > MAX_CACHED_CANDIDATES:
        _candidates.popitem(last=False)


def _session(search_id: str) -> SearchSession:
    session = _sessions.get(search_id)
    if session is None:
        session = get_repository().load_session(search_id)
        if session is not None:
            session = _sessions.adopt(session)
    if session is None:
        raise ToolError(
            f"Unknown search_id {search_id!r}. It is not in this session nor in the local database: "
            "run `search_references` again."
        )
    return session


def _candidate(candidate_id: str) -> tuple[SearchSession | None, Candidate]:
    found = _sessions.candidate(candidate_id)
    if found:
        return found
    cached = _candidates.get(candidate_id)
    if cached is not None:
        return None, cached
    stored = get_repository().find_candidate(candidate_id)
    if stored is None:
        raise ToolError(
            f"Unknown candidate_id {candidate_id!r}. Use an id returned by `search_references`."
        )
    return None, stored[1]


def _project_for(project_id: str | None, project_name: str | None) -> dict | None:
    repository = get_repository()
    if project_id:
        project = repository.get_project(project_id=project_id)
        if project is None:
            raise ToolError(f"Unknown project_id {project_id!r}.")
        return project
    if project_name:
        return repository.create_project(project_name)
    return None


@mcp.tool()
async def engine_status() -> str:
    """Report which search sources, vision transport and storage are actually available.

    Call this first when something fails: it separates "not configured" from "no results".
    """
    config = get_config()
    adapter = PiWebAccessAdapter(config.pi_web_access)
    available, reason = adapter.available()
    repository = get_repository()
    payload = {
        "version": __version__,
        "config_file": str(config.source_path) if config.source_path else None,
        "root": str(config.root),
        "sources": {
            "pi_web_access": {
                "enabled": config.pi_web_access.enabled,
                "available": available,
                "detail": reason,
                "reuses": "pi-web-access MCP server over stdio, with its own credentials and quotas",
            },
        },
        "vision": {
            "server_side_analysis": False,
            "note": (
                "This server cannot see images. It validates that an image decodes, measures it and "
                "returns the bytes through `fetch_reference_image` as a real MCP image block. Only the "
                "agent can confirm what it saw."
            ),
            "max_image_edge": config.vision.max_image_edge,
        },
        "storage": {
            "database_path": str(repository.database.path),
            "persistence_enabled": True,
            "projects": len(repository.list_projects()),
        },
        "limits": {
            "candidate_limit": config.search.candidate_limit,
            "page_fetch_limit": config.search.page_fetch_limit,
            "per_query_limit": config.search.per_query_limit,
            "present_range": [config.search.present_min, config.search.present_max],
        },
    }
    return _json(payload)


@mcp.tool()
async def search_references(
    brief: str,
    queries: list[str] | None = None,
    visual_attributes: list[str] | None = None,
    exclude: list[str] | None = None,
    limit: int | None = None,
    sources: list[str] | None = None,
    project_id: str | None = None,
    project_name: str | None = None,
) -> str:
    """Search real visual references and return traceable candidates.

    Each candidate carries the original page URL, a verified image URL, dimensions, dominant
    colours and how the image was found. Results that could not be verified are returned with
    an explicit `status` and reason instead of being dropped silently.

    Args:
        brief: The design brief in the user's words, used to build a query when none is given.
        queries: Explicit search queries; at most three are used.
        visual_attributes: Attributes to add to the query, e.g. "swiss grid", "risograph".
        exclude: Terms or styles to avoid.
        limit: Maximum candidates to return (capped by configuration).
        sources: Source names to use; defaults to every enabled source.
        project_id: Existing project to attach this session to.
        project_name: Project to create or reuse for this session.
    """
    config = get_config()
    request = DiscoveryRequest(
        brief=(brief or "").strip(),
        queries=[query.strip() for query in (queries or []) if query and query.strip()][:3],
        visual_attributes=[item for item in (visual_attributes or []) if item],
        exclude=[item for item in (exclude or []) if item],
        limit=max(1, limit) if limit else None,
        sources=sources,
    )
    if not request.brief and not request.queries:
        raise ToolError("Provide a brief or at least one query.")
    project = _project_for(project_id, project_name)
    outcome = await discover_references(config, request)
    _remember(outcome)
    session = _sessions.create(
        brief=request.brief,
        queries=outcome.queries,
        attributes=request.visual_attributes,
        exclude=request.exclude,
        outcome=outcome,
        project_id=project["id"] if project else None,
    )
    get_repository().save_session(session)
    payload = outcome.compact()
    if project:
        payload["project"] = {"id": project["id"], "name": project["name"]}
    return _json(payload)


@mcp.tool()
async def evaluate_references(search_id: str, candidate_ids: list[str] | None = None) -> str:
    """Score candidates from a search session with transparent, metadata-only heuristics.

    Returns per-candidate scores (0-5) with the evidence behind each one and the explicit
    limitations. This is arithmetic over source metadata and verified image properties, not a
    visual opinion: use `fetch_reference_image` when visual judgement is required.

    Args:
        search_id: Session returned by `search_references`.
        candidate_ids: Optional subset to score; defaults to every usable candidate.
    """
    session = _session(search_id)
    config = get_config()
    repository = get_repository()
    scored = evaluate_session(session, config.selection)
    if candidate_ids:
        wanted = set(candidate_ids)
        scored = [item for item in scored if item[0].candidate_id in wanted]
    records = []
    for candidate, score in scored:
        record = evaluation_record(candidate, score)
        repository.save_evaluation(search_id, candidate.candidate_id, record["method"], record)
        records.append(record)
    payload = {
        "search_id": search_id,
        "method": "heuristic_v1",
        "analysis_origin": "metadata_heuristics",
        "count": len(records),
        "weights": {
            "relevance": config.selection.relevance,
            "visual_quality": config.selection.visual_quality,
            "usefulness": config.selection.usefulness,
            "novelty": config.selection.novelty,
        },
        "no_visual_analysis": (
            "No image was analysed by this server. Scores use title, snippet, URL, verified image "
            "dimensions, declared pixels and measured colour/brightness only. If you already received "
            "an image, your own visual judgement overrides these numbers and must be labelled as yours."
        ),
        "evaluations": records,
    }
    return _json(payload)


@mcp.tool()
async def present_reference_set(
    search_id: str,
    limit: int | None = None,
    include_previous: bool = False,
) -> str:
    """Package a small set of deliberately different references for the conversation.

    Selection is greedy MMR-style over measured image properties, so it is not simply the top
    of a ranked list. The payload is data for you to present; the user still decides.

    Args:
        search_id: Session returned by `search_references` or `refine_search`.
        limit: How many to present (clamped to the configured 3-5 range).
        include_previous: Set to true to allow candidates already presented in this session.
    """
    session = _session(search_id)
    config = get_config()
    if not include_previous and session.shown:
        shown = set(session.shown)
        session.outcome.candidates = [
            candidate for candidate in session.outcome.candidates if candidate.candidate_id not in shown
        ]
    payload = present_session(
        session,
        limit=limit,
        weights=config.selection,
        present_min=config.search.present_min,
        present_max=config.search.present_max,
    )
    get_repository().save_session(session)
    return _json(payload)


@mcp.tool()
async def refine_search(
    search_id: str,
    mode: str,
    instruction: str,
    limit: int | None = None,
) -> str:
    """Continue a search with the same briefing and one changed dimension.

    Args:
        search_id: Session to refine; its briefing and exclusions are kept.
        mode: `same` (closer to what was shown), `narrow` (tighten an attribute) or `explore`
            (deliberately different direction).
        instruction: What to change, in the user's words.
        limit: Maximum new candidates to return.
    """
    config = get_config()
    base_session = _session(search_id)
    try:
        plan = plan_refinement(base_session, mode, instruction)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    if not plan.queries:
        raise ToolError("The refinement produced no usable query; rephrase the instruction.")

    outcome = await discover_references(
        config,
        DiscoveryRequest(
            brief=plan.queries[0],
            queries=plan.queries,
            visual_attributes=base_session.attributes,
            exclude=plan.exclude,
            limit=max(1, limit) if limit else None,
        ),
    )
    seen = previous_pages(base_session)
    fresh = [candidate for candidate in outcome.candidates if candidate.page_url not in seen]
    dropped = len(outcome.candidates) - len(fresh)
    outcome.candidates = fresh
    if dropped:
        outcome.warnings.append(f"Excluded {dropped} candidate(s) already seen in this search thread.")
    _remember(outcome)
    session = _sessions.create(
        brief=base_session.brief,
        queries=plan.queries,
        attributes=base_session.attributes,
        exclude=plan.exclude,
        outcome=outcome,
        project_id=base_session.project_id,
        refined_from=base_session.search_id,
        refinement_mode=plan.mode,
    )
    get_repository().save_session(session)
    payload = outcome.compact()
    payload["refinement"] = plan.as_dict() | {"refined_from": base_session.search_id}
    return _json(payload)


@mcp.tool()
async def fetch_reference_image(
    candidate_id: str | None = None,
    reference_id: str | None = None,
    image_url: str | None = None,
    max_edge: int | None = None,
) -> list:
    """Return a real image as an MCP image block so the agent can actually see it.

    Use it before describing any candidate visually. Provide a `candidate_id`, a saved
    `reference_id`, or an explicit `image_url` that came from a traceable candidate.

    Args:
        candidate_id: Candidate returned by `search_references` or `refine_search`.
        reference_id: Reference saved with `save_references`.
        image_url: Explicit image URL, only when it came from a traceable candidate.
        max_edge: Longest edge in pixels after downscaling (bounded by configuration).
    """
    config = get_config()
    candidate: Candidate | None = None
    url = image_url
    if reference_id:
        saved = get_repository().get_reference(reference_id)
        if saved is None:
            raise ToolError(f"Unknown reference_id {reference_id!r}.")
        url = url or saved.image_url
        if not url:
            raise ToolError(f"Reference {reference_id} has no stored image URL.")
    if candidate_id:
        _session_found, candidate = _candidate(candidate_id)
        if not candidate.image_url:
            raise ToolError(
                f"Candidate {candidate_id} has no verified image "
                f"({candidate.exclusion_reason or 'no image was found'})."
            )
        url = url or candidate.image_url
    if not url:
        raise ToolError("Provide candidate_id, reference_id or image_url.")

    vision = config.vision
    if max_edge:
        vision = type(vision)(**{**vision.__dict__, "max_image_edge": max(200, min(int(max_edge), 2048))})
    if not vision.enabled:
        raise ToolError("Vision is disabled in configuration (`vision.enabled = false`).")

    try:
        resource = await fetch_image_bytes(url, config.http, max_bytes=vision.max_image_bytes)
        data, mime = prepare_for_model(resource.content, vision)
    except FetchError as exc:
        raise ToolError(str(exc)) from exc

    metadata = {
        "image_url": url,
        "candidate_id": candidate.candidate_id if candidate else None,
        "reference_id": reference_id,
        "page_url": candidate.page_url if candidate else None,
        "title": candidate.title if candidate else None,
        "source": candidate.source if candidate else None,
        "mime_type": mime,
        "bytes": len(data),
        "note": (
            "The attached image is the real resource, downscaled for the model. A visual description "
            "must come from this image, not from these metadata."
        ),
    }
    return [_json(metadata), Image(data=data, format="jpeg")]


@mcp.tool()
async def save_references(
    project_name: str | None = None,
    project_id: str | None = None,
    candidate_ids: list[str] | None = None,
    references: list[dict] | None = None,
    notes: str | None = None,
) -> str:
    """Persist only the references the user chose or authorized.

    No image file is downloaded: the original page URL, the image URL and the compact card are
    stored. Re-saving the same page updates its card instead of duplicating it.

    Args:
        project_name: Project to create or reuse. Recommended: name it after the active work.
        project_id: Existing project id, when one is already known.
        candidate_ids: Candidates to save with their metadata only.
        references: Richer entries, each with `candidate_id` plus optional `why_selected`,
            `problem`, `method`, `transferable_lesson`, `cautions`.
        notes: Free-form note stored once for this save call.
    """
    project = _project_for(project_id, project_name)
    if project is None:
        raise ToolError("Provide project_name (or project_id) so saved references have an owner.")

    entries: list[dict] = []
    for candidate_id in candidate_ids or []:
        entries.append({"candidate_id": candidate_id})
    for entry in references or []:
        if not isinstance(entry, dict) or not entry.get("candidate_id"):
            raise ToolError("Each `references` entry needs a `candidate_id`.")
        entries.append(entry)
    if not entries:
        raise ToolError("Provide candidate_ids or references to save.")

    repository = get_repository()
    saved: list[dict] = []
    unresolved: list[str] = []
    for entry in entries:
        candidate_id = str(entry["candidate_id"])
        try:
            _session_found, candidate = _candidate(candidate_id)
        except ToolError:
            unresolved.append(candidate_id)
            continue
        analysis = {key: entry[key] for key in (
            "why_selected", "problem", "method", "transferable_lesson", "cautions", "analysis_origin"
        ) if entry.get(key)}
        reference = repository.save_reference(project_id=project["id"], candidate=candidate, analysis=analysis, notes=notes)
        saved.append(reference.compact())
    if unresolved:
        raise ToolError(
            f"Unknown candidate id(s): {', '.join(unresolved)}. Nothing was saved for them; "
            f"{len(saved)} reference(s) were saved before the error."
        )
    return _json(
        {
            "project": {"id": project["id"], "name": project["name"]},
            "saved": saved,
            "count": len(saved),
            "image_policy": "URLs only; no image file was copied locally.",
        }
    )


@mcp.tool()
async def get_project_references(
    project_id: str | None = None,
    project_name: str | None = None,
    source: str | None = None,
    limit: int = 50,
) -> str:
    """Read the compact cards saved for a project; images stay on demand.

    Args:
        project_id: Existing project id.
        project_name: Project name, when the id is unknown.
        source: Optional source filter, e.g. `pi_web_access`.
        limit: Maximum cards to return (default 50).
    """
    project = _project_for(project_id, project_name)
    if project is None:
        raise ToolError("Provide project_id or project_name.")
    repository = get_repository()
    saved = repository.project_references(project["id"], source=source, limit=max(1, min(limit, 200)))
    sessions = repository.list_sessions(project["id"], limit=10)
    return _json(
        {
            "project": {"id": project["id"], "name": project["name"]},
            "count": len(saved),
            "references": [reference.compact() for reference in saved],
            "recent_sessions": sessions,
            "note": (
                "Cards are compact on purpose. Call fetch_reference_image(reference_id=...) only for the "
                "references the current task needs; URLs may expire, and that failure is reported."
            ),
        }
    )


@mcp.tool()
async def list_projects() -> str:
    """List local projects with their reference counts."""
    return _json({"projects": get_repository().list_projects()})


def main() -> None:
    try:
        mcp.run()
    except KeyboardInterrupt:  # pragma: no cover
        sys.exit(0)


if __name__ == "__main__":  # pragma: no cover
    main()
