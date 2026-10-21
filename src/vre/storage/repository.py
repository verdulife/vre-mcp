"""Repositories for projects, sessions, candidates and saved references.

No image file is copied here: a saved reference keeps its original page URL, the image URL
and the compact card of the specification. Duplicated facts stay in one table.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from ..models import Candidate, ImageInfo, SearchOutcome, utc_now
from ..workflow.sessions import SearchSession
from .database import Database


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


@dataclass
class SavedReference:
    reference_id: str
    source: str
    page_url: str
    image_url: str | None
    title: str
    creator: str | None
    why_selected: str | None
    problem: str | None
    method: str | None
    transferable_lesson: str | None
    cautions: str | None
    analysis_origin: str
    notes: str | None
    created_at: str

    def compact(self) -> dict[str, Any]:
        return {
            "reference_id": self.reference_id,
            "source": self.source,
            "page_url": self.page_url,
            "image_url": self.image_url,
            "title": self.title,
            "creator": self.creator,
            "why_selected": self.why_selected,
            "analysis_origin": self.analysis_origin,
            "created_at": self.created_at,
            "fetch_image": f"fetch_reference_image(reference_id='{self.reference_id}')",
        }


class Repository:
    def __init__(self, database: Database) -> None:
        self.database = database
        database.initialize()

    # -- projects ---------------------------------------------------------
    def create_project(self, name: str, notes: str | None = None) -> dict[str, Any]:
        cleaned = (name or "").strip()
        if not cleaned:
            raise ValueError("A project name is required.")
        connection = self.database.connection
        existing = connection.execute("SELECT * FROM projects WHERE name = ?", (cleaned,)).fetchone()
        if existing:
            return dict(existing)
        project_id = "proj_" + uuid.uuid4().hex[:10]
        created_at = utc_now()
        with connection:
            connection.execute(
                "INSERT INTO projects (id, name, notes, created_at) VALUES (?, ?, ?, ?)",
                (project_id, cleaned, notes, created_at),
            )
        return {"id": project_id, "name": cleaned, "notes": notes, "created_at": created_at}

    def get_project(self, *, project_id: str | None = None, name: str | None = None) -> dict[str, Any] | None:
        connection = self.database.connection
        if project_id:
            row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        elif name:
            row = connection.execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()
        else:
            return None
        return dict(row) if row else None

    def list_projects(self) -> list[dict[str, Any]]:
        rows = self.database.connection.execute(
            "SELECT p.*, COUNT(pr.reference_id) AS reference_count FROM projects p "
            "LEFT JOIN project_references pr ON pr.project_id = p.id GROUP BY p.id ORDER BY p.created_at"
        ).fetchall()
        return [dict(row) for row in rows]

    # -- sessions ---------------------------------------------------------
    def save_session(self, session: SearchSession) -> None:
        connection = self.database.connection
        with connection:
            connection.execute(
                "INSERT OR REPLACE INTO search_sessions "
                "(id, project_id, brief, queries, attributes, exclude, warnings, errors, refined_from, "
                " refinement_mode, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session.search_id,
                    session.project_id,
                    session.brief,
                    _json(session.queries),
                    _json(session.attributes),
                    _json(session.exclude),
                    _json(session.outcome.warnings),
                    _json(session.outcome.errors),
                    session.refined_from,
                    session.refinement_mode,
                    session.created_at,
                ),
            )
            for candidate in session.outcome.candidates:
                connection.execute(
                    "INSERT OR REPLACE INTO candidates "
                    "(session_id, candidate_id, title, page_url, source, query, snippet, creator, "
                    " metadata_confidence, status, exclusion_reason, image_json, retrieved_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        session.search_id,
                        candidate.candidate_id,
                        candidate.title,
                        candidate.page_url,
                        candidate.source,
                        candidate.query,
                        candidate.snippet,
                        candidate.creator,
                        candidate.metadata_confidence,
                        candidate.status,
                        candidate.exclusion_reason,
                        _json(candidate.image.__dict__) if candidate.image else None,
                        candidate.retrieved_at,
                    ),
                )

    def load_session(self, search_id: str) -> SearchSession | None:
        connection = self.database.connection
        row = connection.execute("SELECT * FROM search_sessions WHERE id = ?", (search_id,)).fetchone()
        if row is None:
            return None
        candidates = [
            _candidate_from_row(candidate_row)
            for candidate_row in connection.execute(
                "SELECT * FROM candidates WHERE session_id = ? ORDER BY rowid", (search_id,)
            ).fetchall()
        ]
        outcome = SearchOutcome(
            brief=row["brief"],
            queries=json.loads(row["queries"]),
            candidates=candidates,
            warnings=json.loads(row["warnings"]),
            errors=json.loads(row["errors"]),
            session_id=search_id,
        )
        return SearchSession(
            search_id=search_id,
            brief=row["brief"],
            queries=outcome.queries,
            attributes=json.loads(row["attributes"]),
            exclude=json.loads(row["exclude"]),
            outcome=outcome,
            project_id=row["project_id"],
            created_at=row["created_at"],
            refined_from=row["refined_from"],
            refinement_mode=row["refinement_mode"],
        )

    def list_sessions(self, project_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        connection = self.database.connection
        if project_id:
            rows = connection.execute(
                "SELECT id, brief, queries, created_at, refinement_mode FROM search_sessions "
                "WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT id, brief, queries, created_at, refinement_mode FROM search_sessions "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{**dict(row), "queries": json.loads(row["queries"])} for row in rows]

    def find_candidate(self, candidate_id: str) -> tuple[str, Candidate] | None:
        row = self.database.connection.execute(
            "SELECT * FROM candidates WHERE candidate_id = ? ORDER BY rowid DESC LIMIT 1", (candidate_id,)
        ).fetchone()
        if row is None:
            return None
        return row["session_id"], _candidate_from_row(row)

    def save_evaluation(self, search_id: str, candidate_id: str, method: str, payload: dict) -> None:
        connection = self.database.connection
        with connection:
            connection.execute(
                "INSERT OR REPLACE INTO evaluations (session_id, candidate_id, method, payload, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (search_id, candidate_id, method, _json(payload), utc_now()),
            )

    # -- saved references -------------------------------------------------
    def save_reference(
        self,
        project_id: str,
        candidate: Candidate,
        *,
        analysis: dict[str, Any] | None = None,
        notes: str | None = None,
    ) -> SavedReference:
        connection = self.database.connection
        analysis = analysis or {}
        created_at = utc_now()
        existing = connection.execute(
            "SELECT * FROM references_ WHERE page_url = ?", (candidate.page_url,)
        ).fetchone()
        if existing:
            reference_id = existing["reference_id"]
            with connection:
                connection.execute(
                    "UPDATE references_ SET image_url = COALESCE(?, image_url), "
                    "why_selected = COALESCE(?, why_selected), problem = COALESCE(?, problem), "
                    "method = COALESCE(?, method), transferable_lesson = COALESCE(?, transferable_lesson), "
                    "cautions = COALESCE(?, cautions), notes = COALESCE(?, notes) WHERE reference_id = ?",
                    (
                        candidate.image_url,
                        analysis.get("why_selected"),
                        analysis.get("problem"),
                        analysis.get("method"),
                        analysis.get("transferable_lesson"),
                        analysis.get("cautions"),
                        notes,
                        reference_id,
                    ),
                )
        else:
            reference_id = "ref_" + uuid.uuid4().hex[:10]
            with connection:
                connection.execute(
                    "INSERT INTO references_ (reference_id, source, page_url, image_url, title, creator, "
                    "why_selected, problem, method, transferable_lesson, cautions, analysis_origin, notes, "
                    "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        reference_id,
                        candidate.source,
                        candidate.page_url,
                        candidate.image_url,
                        candidate.title,
                        candidate.creator,
                        analysis.get("why_selected"),
                        analysis.get("problem"),
                        analysis.get("method"),
                        analysis.get("transferable_lesson"),
                        analysis.get("cautions"),
                        analysis.get("analysis_origin") or "model_observation",
                        notes,
                        created_at,
                    ),
                )
        with connection:
            connection.execute(
                "INSERT OR IGNORE INTO project_references (project_id, reference_id, created_at) "
                "VALUES (?, ?, ?)",
                (project_id, reference_id, created_at),
            )
        row = connection.execute("SELECT * FROM references_ WHERE reference_id = ?", (reference_id,)).fetchone()
        return SavedReference(**dict(row))

    def get_reference(self, reference_id: str) -> SavedReference | None:
        row = self.database.connection.execute(
            "SELECT * FROM references_ WHERE reference_id = ?", (reference_id,)
        ).fetchone()
        return SavedReference(**dict(row)) if row else None

    def project_references(
        self,
        project_id: str,
        *,
        source: str | None = None,
        limit: int = 50,
    ) -> list[SavedReference]:
        connection = self.database.connection
        query = (
            "SELECT r.* FROM references_ r JOIN project_references pr ON pr.reference_id = r.reference_id "
            "WHERE pr.project_id = ?"
        )
        params: list[Any] = [project_id]
        if source:
            query += " AND r.source = ?"
            params.append(source)
        query += " ORDER BY pr.created_at DESC LIMIT ?"
        params.append(limit)
        return [SavedReference(**dict(row)) for row in connection.execute(query, params).fetchall()]


def _candidate_from_row(row) -> Candidate:
    image = None
    if row["image_json"]:
        data = json.loads(row["image_json"])
        image = ImageInfo(**data)
    return Candidate(
        candidate_id=row["candidate_id"],
        title=row["title"],
        page_url=row["page_url"],
        source=row["source"],
        query=row["query"],
        snippet=row["snippet"],
        image=image,
        creator=row["creator"],
        metadata_confidence=row["metadata_confidence"],
        status=row["status"],
        exclusion_reason=row["exclusion_reason"],
        retrieved_at=row["retrieved_at"],
    )
