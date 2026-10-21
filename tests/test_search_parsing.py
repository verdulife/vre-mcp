"""Search backend parsing, source failures and incomplete results (spec §11, §17)."""

from __future__ import annotations

import unittest

from vre.sources.pi_web_access import parse_search_text

SOURCES_BLOCK = """**Provider:** exa

Brutalist event poster with red text # A poster in red condensed capitals
Source: Brutalist event poster (https://example.test/brutalist-poster)

Swiss grid system # A modular grid for A0 posters
Source: Swiss grid system (https://example.test/swiss-grid)

---

**Sources:**
1. Brutalist event poster
   https://example.test/brutalist-poster

2. Swiss grid system
   https://example.test/swiss-grid
---
Full search results are stored as responseId "abc".
"""


class ParseSearchTextTests(unittest.TestCase):
    def test_sources_block_is_parsed_in_order_with_snippets(self):
        results, provider, warnings = parse_search_text(SOURCES_BLOCK, "brutalist poster")
        self.assertEqual(provider, "exa")
        self.assertEqual(warnings, [])
        self.assertEqual([item.page_url for item in results], [
            "https://example.test/brutalist-poster",
            "https://example.test/swiss-grid",
        ])
        self.assertIn("red condensed capitals", results[0].snippet)
        self.assertEqual(results[0].query, "brutalist poster")

    def test_provider_answer_without_sources_reports_inability(self):
        text = "**Provider:** generated\n\nA written answer with no links.\n"
        results, provider, warnings = parse_search_text(text)
        self.assertEqual(results, [])
        self.assertEqual(provider, "generated")
        self.assertTrue(warnings and "no traceable results" in warnings[0])

    def test_empty_text_is_not_silently_successful(self):
        results, _provider, warnings = parse_search_text("   ")
        self.assertEqual(results, [])
        self.assertEqual(len(warnings), 1)

    def test_duplicate_source_lines_collapse(self):
        text = SOURCES_BLOCK + "\n3. Brutalist event poster again\n   https://example.test/brutalist-poster\n"
        results, _provider, _warnings = parse_search_text(text)
        self.assertEqual(len({item.page_url for item in results}), len(results))


class AdapterAvailabilityTests(unittest.TestCase):
    def test_disabled_source_reports_reason_instead_of_results(self):
        from vre.config import PiWebAccessConfig
        from vre.sources.pi_web_access import PiWebAccessAdapter

        adapter = PiWebAccessAdapter(PiWebAccessConfig(enabled=False))
        available, reason = adapter.available()
        self.assertFalse(available)
        self.assertIn("disabled", reason or "")

    def test_missing_server_path_is_reported(self):
        from vre.config import PiWebAccessConfig
        from vre.sources.pi_web_access import PiWebAccessAdapter

        adapter = PiWebAccessAdapter(PiWebAccessConfig(server_path="/definitely/missing/mcp-cli.js"))
        available, reason = adapter.available()
        self.assertFalse(available)
        self.assertIn("not found", reason or "")


if __name__ == "__main__":
    unittest.main()
