"""Search sessions: what was asked, which candidates exist, what was already shown.

The store is the boundary that later gains SQLite persistence; the MCP layer only depends on
this interface, so adding the database does not change the tools.
"""

from __future__ import annotations

import uuid
from collections import OrderedDict
from dataclasses import dataclass, field

from ..models import Candidate, SearchOutcome, utc_now

MAX_SESSIONS = 50


@dataclass
class SearchSession:
    search_id: str
    brief: str
    queries: list[str]
    attributes: list[str]
    exclude: list[str]
    outcome: SearchOutcome
    project_id: str | None = None
    shown: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    refined_from: str | None = None
    refinement_mode: str | None = None

    def usable(self) -> list[Candidate]:
        return [candidate for candidate in self.outcome.candidates if candidate.status == "ok"]

    def candidate(self, candidate_id: str) -> Candidate | None:
        for item in self.outcome.candidates:
            if item.candidate_id == candidate_id:
                return item
        return None


class SessionStore:
    def __init__(self, max_sessions: int = MAX_SESSIONS) -> None:
        self._sessions: "OrderedDict[str, SearchSession]" = OrderedDict()
        self._max = max_sessions

    def create(
        self,
        *,
        brief: str,
        queries: list[str],
        attributes: list[str],
        exclude: list[str],
        outcome: SearchOutcome,
        project_id: str | None = None,
        refined_from: str | None = None,
        refinement_mode: str | None = None,
    ) -> SearchSession:
        search_id = "sess_" + uuid.uuid4().hex[:12]
        session = SearchSession(
            search_id=search_id,
            brief=brief,
            queries=queries,
            attributes=attributes,
            exclude=exclude,
            outcome=outcome,
            project_id=project_id,
            refined_from=refined_from,
            refinement_mode=refinement_mode,
        )
        outcome.session_id = search_id
        self._sessions[search_id] = session
        while len(self._sessions) > self._max:
            self._sessions.popitem(last=False)
        return session

    def get(self, search_id: str) -> SearchSession | None:
        return self._sessions.get(search_id)

    def adopt(self, session: SearchSession) -> SearchSession:
        """Insert a session hydrated from persistence so later calls find it in memory."""
        self._sessions[session.search_id] = session
        self._sessions.move_to_end(session.search_id)
        while len(self._sessions) > self._max:
            self._sessions.popitem(last=False)
        return session

    def latest(self) -> SearchSession | None:
        if not self._sessions:
            return None
        return next(reversed(self._sessions.values()))

    def candidate(self, candidate_id: str) -> tuple[SearchSession, Candidate] | None:
        for session in reversed(self._sessions.values()):
            found = session.candidate(candidate_id)
            if found is not None:
                return session, found
        return None

    def mark_shown(self, search_id: str, candidate_ids: list[str]) -> None:
        session = self._sessions.get(search_id)
        if session is None:
            return
        for candidate_id in candidate_ids:
            if candidate_id not in session.shown:
                session.shown.append(candidate_id)

    def clear(self) -> None:
        self._sessions.clear()
