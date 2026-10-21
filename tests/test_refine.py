"""Refinement planning keeps the briefing and changes one dimension (spec §6.G)."""

from __future__ import annotations

import unittest

from vre.models import SearchOutcome
from vre.workflow.refine import plan_refinement, previous_pages
from vre.workflow.sessions import SessionStore
from tests.fixtures import make_candidate


def _session(queries=("brutalist festival poster",), exclude=("pastel",)):
    outcome = SearchOutcome(
        brief="Cartel para un festival de música electrónica",
        queries=list(queries),
        candidates=[make_candidate("c1", "https://a.test/one"), make_candidate("c2", "https://a.test/two")],
    )
    return SessionStore().create(
        brief=outcome.brief,
        queries=outcome.queries,
        attributes=["high contrast"],
        exclude=list(exclude),
        outcome=outcome,
    )


class RefinementPlanTests(unittest.TestCase):
    def test_same_mode_keeps_the_original_query(self):
        plan = plan_refinement(_session(), "same", "more like the first one")
        self.assertEqual(plan.mode, "same")
        self.assertTrue(plan.queries[0].startswith("brutalist festival poster"))
        self.assertIn("more like the first one", plan.queries[0])
        self.assertEqual(plan.exclude, ["pastel"])

    def test_narrow_mode_keeps_the_briefing(self):
        plan = plan_refinement(_session(), "narrow", "editorial white space")
        self.assertIn("editorial", plan.queries[0])
        self.assertIn("festival", plan.queries[0].lower())

    def test_explore_mode_drops_the_original_query(self):
        plan = plan_refinement(_session(), "explore", "editorial layout, quieter")
        self.assertNotIn("brutalist", plan.queries[0])
        self.assertIn("editorial", plan.queries[0])

    def test_unknown_mode_and_empty_instruction_are_rejected(self):
        session = _session()
        with self.assertRaises(ValueError):
            plan_refinement(session, "sideways", "x")
        with self.assertRaises(ValueError):
            plan_refinement(session, "same", "   ")

    def test_previous_pages_are_tracked_for_deduplication(self):
        self.assertEqual(previous_pages(_session()), {"https://a.test/one", "https://a.test/two"})


if __name__ == "__main__":
    unittest.main()
