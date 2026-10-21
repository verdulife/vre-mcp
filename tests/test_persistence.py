"""Persistence and retrieval (spec §9, §10, §17)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vre.models import SearchOutcome
from vre.storage import Database, Repository
from vre.workflow.sessions import SessionStore
from tests.fixtures import make_candidate


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.tmp.name) / "library.sqlite")
        self.repository = Repository(self.database)

    def tearDown(self):
        self.database.close()
        self.tmp.cleanup()

    def _session(self, candidates):
        outcome = SearchOutcome(brief="poster brief", queries=["poster query"], candidates=candidates)
        return SessionStore().create(
            brief=outcome.brief, queries=outcome.queries, attributes=["brutal"], exclude=["pastel"], outcome=outcome
        )

    def test_schema_is_created_once_with_a_version(self):
        self.repository.database.initialize()
        row = self.repository.database.connection.execute("SELECT version FROM schema_version").fetchone()
        self.assertEqual(row["version"], 1)

    def test_session_round_trip_keeps_candidates_and_image_metadata(self):
        session = self._session([make_candidate("c1"), make_candidate("c2", with_image=False, status="no_image")])
        self.repository.save_session(session)
        loaded = self.repository.load_session(session.search_id)
        assert loaded is not None
        self.assertEqual(loaded.brief, "poster brief")
        self.assertEqual(loaded.exclude, ["pastel"])
        self.assertEqual(len(loaded.outcome.candidates), 2)
        first = loaded.outcome.candidates[0]
        assert first.image is not None
        self.assertEqual(first.image.width, 1200)
        self.assertEqual(first.image.dominant_colors, ["#111111", "#dd2222"])
        self.assertEqual(loaded.outcome.candidates[1].status, "no_image")

    def test_saved_reference_is_idempotent_per_page(self):
        session = self._session([make_candidate("c1")])
        project = self.repository.create_project("Festival poster")
        candidate = session.outcome.candidates[0]
        first = self.repository.save_reference(project["id"], candidate, analysis={"why_selected": "user picked it"})
        second = self.repository.save_reference(project["id"], candidate, analysis={"cautions": "check resolution"})
        self.assertEqual(first.reference_id, second.reference_id)
        cards = self.repository.project_references(project["id"])
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].why_selected, "user picked it")
        self.assertEqual(cards[0].cautions, "check resolution")
        self.assertEqual(cards[0].creator, None)

    def test_project_reuse_and_filters(self):
        project = self.repository.create_project("Festival poster")
        same = self.repository.create_project("Festival poster")
        self.assertEqual(project["id"], same["id"])
        other = self.repository.create_project("Editorial book")
        session = self._session([make_candidate("c1", page_url="https://a.test/1")])
        candidate = session.outcome.candidates[0]
        self.repository.save_reference(project["id"], candidate)
        self.repository.save_reference(other["id"], candidate)
        self.assertEqual(len(self.repository.project_references(project["id"])), 1)
        self.assertEqual(len(self.repository.project_references(project["id"], source="nope")), 0)
        self.assertEqual(len(self.repository.list_projects()), 2)

    def test_unknown_reference_lookup_is_none(self):
        self.assertIsNone(self.repository.get_reference("ref_missing"))

    def test_find_candidate_by_id_across_sessions(self):
        session = self._session([make_candidate("c1")])
        self.repository.save_session(session)
        found = self.repository.find_candidate("c1")
        assert found is not None
        self.assertEqual(found[0], session.search_id)
        self.assertEqual(found[1].candidate_id, "c1")

    def test_evaluation_payload_is_stored_per_method(self):
        session = self._session([make_candidate("c1")])
        self.repository.save_session(session)
        self.repository.save_evaluation(session.search_id, "c1", "heuristic_v1", {"overall": 3.2})
        self.repository.save_evaluation(session.search_id, "c1", "heuristic_v1", {"overall": 3.5})
        row = self.repository.database.connection.execute(
            "SELECT payload FROM evaluations WHERE session_id = ? AND candidate_id = ?", (session.search_id, "c1")
        ).fetchone()
        self.assertIn("3.5", row["payload"])


if __name__ == "__main__":
    unittest.main()
