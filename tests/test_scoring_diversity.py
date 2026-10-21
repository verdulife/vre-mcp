"""Scoring, diversity and honest presentation (spec §6.D, §8, §17)."""

from __future__ import annotations

import unittest

from vre.config import SelectionWeights
from vre.evaluation.diversity import color_family, distance, select_diverse
from vre.evaluation.scoring import score_candidate
from vre.models import SearchOutcome
from vre.workflow.present import present_session
from vre.workflow.sessions import SessionStore
from tests.fixtures import make_candidate


def _session(candidates):
    store = SessionStore()
    outcome = SearchOutcome(brief="brutalist festival poster", queries=["brutalist festival poster"], candidates=candidates)
    return store.create(
        brief=outcome.brief, queries=outcome.queries, attributes=[], exclude=[], outcome=outcome
    )


class ScoringTests(unittest.TestCase):
    def test_relevance_reacts_to_brief_terms(self):
        matching = make_candidate("match", title="Brutalist festival poster typography")
        unrelated = make_candidate(
            "nope", title="Corporate banking website", snippet="Quarterly earnings report"
        )
        brief = "brutalist festival poster"
        self.assertGreater(
            score_candidate(matching, brief=brief).relevance,
            score_candidate(unrelated, brief=brief).relevance,
        )

    def test_unverified_image_scores_low_and_says_why(self):
        candidate = make_candidate("noimg", with_image=False, status="no_image")
        score = score_candidate(candidate, brief="poster")
        self.assertLessEqual(score.visual_quality, 1.0)
        self.assertTrue(any("No verified image" in item for item in score.limitations))

    def test_social_card_is_flagged_not_trusted(self):
        card = make_candidate("card", discovery="og:image")
        body = make_candidate("body", discovery="img")
        card_score = score_candidate(card, brief="poster")
        body_score = score_candidate(body, brief="poster")
        self.assertGreater(body_score.usefulness, card_score.usefulness)
        self.assertTrue(any("social card" in item for item in card_score.limitations))

    def test_weights_are_normalized_before_use(self):
        candidate = make_candidate("x")
        heavy = score_candidate(candidate, brief="poster", weights=SelectionWeights(10, 1, 1, 1))
        balanced = score_candidate(candidate, brief="poster", weights=SelectionWeights(1, 1, 1, 1))
        self.assertLess(heavy.overall, 5.01)
        self.assertNotEqual(heavy.overall, balanced.overall)

    def test_color_families(self):
        self.assertEqual(color_family("#000000"), "black")
        self.assertEqual(color_family("#ffffff"), "white")
        self.assertEqual(color_family("#d32f2f"), "red")
        self.assertEqual(color_family("#2f6fd3"), "blue")
        self.assertEqual(color_family("not-a-colour"), "unknown")


class DiversityTests(unittest.TestCase):
    def test_near_duplicates_are_far_closer_than_different_directions(self):
        a = make_candidate("a", width=1200, height=630, colors=("#151318", "#7b5858"), brightness=0.17)
        b = make_candidate("b", width=1200, height=630, colors=("#151318", "#7b5858"), brightness=0.17)
        c = make_candidate("c", width=1000, height=1400, colors=("#ffffff", "#ffcc00"), brightness=0.8)
        self.assertLess(distance(a, b), 0.05)
        self.assertGreater(distance(a, c), 0.4)

    def test_selection_prefers_different_directions_over_pure_ranking(self):
        base = make_candidate("base", width=1200, height=630, colors=("#111111", "#dd2222"), brightness=0.2,
                              title="Brutalist festival poster A")
        clone = make_candidate("clone", width=1200, height=630, colors=("#111111", "#dd2222"), brightness=0.21,
                               title="Brutalist festival poster B")
        light = make_candidate("light", width=1000, height=1400, colors=("#ffffff", "#ffd400"), brightness=0.85,
                               title="Swiss editorial poster grid")
        scorer = lambda candidate: score_candidate(candidate, brief="brutalist festival poster")
        pool = [(base, scorer(base)), (clone, scorer(clone)), (light, scorer(light))]
        picks = select_diverse(pool, 2)
        chosen = [pick.candidate.candidate_id for pick in picks]
        self.assertEqual(chosen[0], "base")
        self.assertIn("light", chosen)
        self.assertNotIn("clone", chosen)
        self.assertIsNotNone(picks[1].distance_to_selected)

    def test_fewer_than_three_usable_is_reported_not_filled(self):
        session = _session([make_candidate("only")])
        payload = present_session(
            session, limit=5, weights=None, present_min=3, present_max=5
        )
        self.assertEqual(payload["count"], 1)
        self.assertTrue(any("minimum" in note for note in payload["notes"]))

    def test_presentation_carries_links_cautions_and_verify_hint(self):
        session = _session([make_candidate("x"), make_candidate("y", discovery="img", title="Grid poster")])
        payload = present_session(session, limit=3, weights=None, present_min=3, present_max=5)
        item = payload["presentation"][0]
        for key in ("page_url", "image_url", "source", "why_selected", "measured_observations", "cautions"):
            self.assertIn(key, item)
        self.assertIn("fetch_reference_image", item["verify_visually"])
        self.assertTrue(any("No visual" in limit for limit in item["cautions"]))

    def test_table_rows_are_ready_to_present(self):
        session = _session([
            make_candidate("x", title="Polly James | blind emboss"),
            make_candidate("y", discovery="img", title="Grid poster"),
        ])
        payload = present_session(session, limit=3, weights=None, present_min=3, present_max=5)
        rows = payload["presentation_table"]
        self.assertEqual(len(rows), payload["count"])
        first = rows[0]
        self.assertEqual(first["image_link"], f"[Ver imagen]({first['image_url']})")
        self.assertRegex(first["valuation"], r"^\d\.\d/5$")
        self.assertIn("Imagen | Descripción | Valoración", payload["table_markdown"])
        self.assertEqual(len(payload["table_markdown"].splitlines()), len(rows) + 2)
        piped = [row for row in rows if row["candidate_id"] == "x"][0]
        self.assertIn("Polly James \\| blind emboss", piped["description"])
        self.assertEqual(first["candidate_id"], payload["presentation"][0]["candidate_id"])

    def test_empty_pool_says_so(self):
        session = _session([])
        payload = present_session(session, limit=5, weights=None, present_min=3, present_max=5)
        self.assertEqual(payload["presentation"], [])
        self.assertTrue(payload["notes"])


class PresentationSizeGateTests(unittest.TestCase):
    """An image too small to judge is left out instead of being handed to the agent."""

    def test_small_verified_images_are_left_out_with_one_note(self):
        session = _session(
            [
                make_candidate("thin", width=400, height=131, title="Thin banner crop"),
                make_candidate("flat", width=412, height=241, title="Small card crop"),
                make_candidate("good", width=1200, height=630, title="Festival poster full bleed"),
            ]
        )
        payload = present_session(session, limit=5, weights=None, present_min=3, present_max=5)
        presented = [item["candidate_id"] for item in payload["presentation"]]
        self.assertEqual(presented, ["good"])
        size_notes = [note for note in payload["notes"] if "were left out" in note]
        self.assertEqual(len(size_notes), 1)
        self.assertIn("2 candidate(s)", size_notes[0])
        self.assertIn("240", size_notes[0])
        self.assertIn("120000", size_notes[0])

    def test_no_size_note_when_every_image_is_large_enough(self):
        session = _session([make_candidate("good", width=1200, height=630)])
        payload = present_session(session, limit=5, weights=None, present_min=3, present_max=5)
        self.assertFalse(any("were left out" in note for note in payload["notes"]))

    def test_presentation_items_declare_verified_mime(self):
        session = _session([make_candidate("good", width=1200, height=630)])
        payload = present_session(session, limit=3, weights=None, present_min=3, present_max=5)
        item = payload["presentation"][0]
        self.assertTrue(item["image_verified"])
        self.assertEqual(item["image_mime"], "image/jpeg")
        self.assertTrue(item["image_url"].endswith("-image.jpg"))


if __name__ == "__main__":
    unittest.main()
