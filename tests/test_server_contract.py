"""MCP tool contract: validation, honest errors, no invented state (spec §5, §7, §17)."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

from mcp.server.fastmcp.exceptions import ToolError

from vre import server


def _isolated_environment(testcase):
    tmp = tempfile.TemporaryDirectory()
    testcase.addCleanup(tmp.cleanup)
    patcher = mock.patch.dict(os.environ, {"VRE_DB_PATH": os.path.join(tmp.name, "library.sqlite")})
    patcher.start()
    testcase.addCleanup(patcher.stop)
    server.reset_state()
    testcase.addCleanup(server.reset_state)
    return tmp


class ContractTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _isolated_environment(self)

    async def test_empty_brief_is_rejected_before_any_search(self):
        with self.assertRaises(ToolError):
            await server.search_references("")

    async def test_unknown_search_id_is_reported(self):
        with self.assertRaises(ToolError) as caught:
            await server.evaluate_references("sess_does_not_exist")
        self.assertIn("Unknown search_id", str(caught.exception))

    async def test_unknown_candidate_id_is_reported(self):
        with self.assertRaises(ToolError) as caught:
            await server.fetch_reference_image(candidate_id="cand_missing")
        self.assertIn("Unknown candidate_id", str(caught.exception))

    async def test_fetch_without_any_identifier_is_reported(self):
        with self.assertRaises(ToolError):
            await server.fetch_reference_image()

    async def test_unknown_reference_id_is_reported(self):
        with self.assertRaises(ToolError) as caught:
            await server.fetch_reference_image(reference_id="ref_missing")
        self.assertIn("Unknown reference_id", str(caught.exception))

    async def test_vision_disabled_refuses_instead_of_pretending(self):
        config = server.get_config()
        server._config = type(config)(**{**config.__dict__, "vision": type(config.vision)(enabled=False)})
        with self.assertRaises(ToolError) as caught:
            await server.fetch_reference_image(image_url="https://example.test/image.jpg")
        self.assertIn("Vision is disabled", str(caught.exception))

    async def test_save_requires_a_project(self):
        with self.assertRaises(ToolError) as caught:
            await server.save_references(candidate_ids=["cand_x"])
        self.assertIn("project_name", str(caught.exception))

    async def test_engine_status_declares_no_server_side_vision(self):
        import json

        payload = json.loads(await server.engine_status())
        self.assertFalse(payload["vision"]["server_side_analysis"])
        self.assertTrue(payload["storage"]["persistence_enabled"])
        self.assertIn("pi_web_access", payload["sources"])
        self.assertNotIn("apiKey", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
