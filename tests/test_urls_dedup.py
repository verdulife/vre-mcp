"""URL normalization and deduplication (spec §6.C, §17)."""

from __future__ import annotations

import unittest

from visual_reference.discovery.deduplication import dedupe_candidates
from visual_reference.urls import dedupe_key, domain_allowed, is_http_url, normalize_url
from tests.fixtures import make_candidate


class NormalizeUrlTests(unittest.TestCase):
    def test_tracking_parameters_and_fragment_are_dropped(self):
        left = normalize_url("HTTPS://Example.TEST/poster/?utm_source=x&id=7#section")
        right = normalize_url("https://example.test/poster?id=7")
        self.assertEqual(left, right)
        self.assertEqual(left, "https://example.test/poster?id=7")

    def test_default_ports_and_trailing_slash_are_normalized(self):
        self.assertEqual(
            normalize_url("http://example.test:80/a/"),
            normalize_url("http://example.test/a"),
        )

    def test_distinct_queries_stay_distinct(self):
        self.assertNotEqual(dedupe_key("https://a.test/x?id=1"), dedupe_key("https://a.test/x?id=2"))

    def test_scheme_gate(self):
        self.assertTrue(is_http_url("https://a.test"))
        for bad in ("file:///etc/passwd", "javascript:alert(1)", "ftp://a.test", "data:image/png;base64,AA"):
            self.assertFalse(is_http_url(bad), bad)

    def test_domain_filtering(self):
        self.assertTrue(domain_allowed("cdn.a.test", ["a.test"], None))
        self.assertFalse(domain_allowed("a.test", None, ["a.test"]))
        self.assertFalse(domain_allowed("evil.test", ["a.test"], None))


class DedupeTests(unittest.TestCase):
    def test_same_page_with_tracking_is_deduplicated(self):
        first = make_candidate("c1", "https://example.test/poster?utm_campaign=z")
        second = make_candidate("c2", "https://example.test/poster")
        kept, removed = dedupe_candidates([first, second])
        self.assertEqual(removed, 1)
        self.assertEqual([candidate.candidate_id for candidate in kept], ["c1"])

    def test_same_image_from_different_pages_is_deduplicated(self):
        first = make_candidate("c1", "https://example.test/a")
        second = make_candidate("c2", "https://example.test/b")
        assert first.image and second.image
        second.image.url = first.image.url
        kept, removed = dedupe_candidates([first, second])
        self.assertEqual(removed, 1)
        self.assertEqual(len(kept), 1)


if __name__ == "__main__":
    unittest.main()
