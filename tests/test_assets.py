"""Static assets: example configuration, MCP wiring and the shipped skill (spec §14, §16, §17)."""

from __future__ import annotations

import json
import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ConfigAssetTests(unittest.TestCase):
    def test_example_config_parses_and_matches_the_loader(self):
        from visual_reference.config import load_config

        data = tomllib.loads((ROOT / "visual-reference.toml.example").read_text(encoding="utf-8"))
        for section in ("search", "vision", "storage", "http", "selection"):
            self.assertIn(section, data)
        config = load_config()
        self.assertGreaterEqual(config.search.present_min, 1)
        self.assertLessEqual(config.search.present_min, config.search.present_max)
        self.assertGreater(config.search.candidate_limit, 0)
        self.assertFalse(data["assets"]["store_original_images"])

    def test_project_mcp_config_points_at_the_server_script(self):
        payload = json.loads((ROOT / ".pi" / "mcp.json").read_text(encoding="utf-8"))
        server = payload["mcpServers"]["visual-reference"]
        self.assertEqual(server["exposure"], "direct")
        self.assertTrue(Path(server["args"][0]).is_file())
        self.assertIn("scripts", server["args"][0])


class SkillAssetTests(unittest.TestCase):
    def setUp(self):
        self.path = ROOT / ".agents" / "skills" / "visual-reference-workflow" / "SKILL.md"
        self.text = self.path.read_text(encoding="utf-8")

    def test_frontmatter_has_name_and_routing_description(self):
        match = re.match(r"^---\n(?P<body>.*?)\n---\n", self.text, re.DOTALL)
        self.assertIsNotNone(match, "SKILL.md must start with frontmatter")
        body = match.group("body")
        self.assertIn("name: visual-reference-workflow", body)
        description = re.search(r"description: \"?(.*?)\"?\n", body)
        assert description is not None
        self.assertIn("Trigger:", description.group(1))

    def test_skill_keeps_the_ten_rules(self):
        required = [
            "fetch_reference_image",
            "never invent",
            "save_references",
            "present_reference_set",
            "engine_status",
            "refine_search",
            "get_project_references",
            "costs the user time",
        ]
        lowered = self.text.lower()
        for needle in required:
            self.assertIn(needle.lower(), lowered, needle)

    def test_skill_does_not_depend_on_another_skill(self):
        self.assertNotIn("/skill:", self.text)


if __name__ == "__main__":
    unittest.main()
