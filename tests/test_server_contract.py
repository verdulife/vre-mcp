"""MCP tool contract: validation, honest errors, no invented state (spec §5, §7, §17)."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from unittest import mock

from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.fastmcp.utilities.types import Image as McpImage
from PIL import Image

from vre import server
from vre.http_safety import FetchError, FetchedResource
from vre.models import SearchOutcome
from tests.fixtures import make_candidate


def _jpeg_bytes(width: int = 640, height: int = 400) -> bytes:
    """A real, decodable JPEG generated locally; no network involved."""
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (210, 80, 60)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _fake_fetch_factory(payload: bytes | Exception):
    async def fake_fetch(url: str, config, *, max_bytes=None, client=None):
        if isinstance(payload, Exception):
            raise payload
        return FetchedResource(
            url=url, final_url=url, status_code=200, content_type="image/jpeg", content=payload
        )

    return fake_fetch


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


class PresentSetAttachmentTests(unittest.IsolatedAsyncioTestCase):
    """`present_reference_set` must hand over the real images, not only their URLs."""

    def setUp(self):
        _isolated_environment(self)
        self.candidates = [
            make_candidate("cand_a", width=1200, height=630, title="Festival poster full bleed"),
            make_candidate(
                "cand_b",
                width=1000,
                height=1400,
                colors=("#ffffff", "#ffd400"),
                brightness=0.85,
                title="Swiss editorial grid",
            ),
            make_candidate(
                "cand_c",
                width=900,
                height=900,
                colors=("#101010", "#33ccaa"),
                brightness=0.55,
                title="Risograph texture study",
            ),
        ]
        outcome = SearchOutcome(
            brief="brutalist festival poster",
            queries=["brutalist festival poster"],
            candidates=list(self.candidates),
        )
        self.session = server._sessions.create(
            brief=outcome.brief,
            queries=outcome.queries,
            attributes=[],
            exclude=[],
            outcome=outcome,
        )

    async def test_compact_payload_declares_verified_mime(self):
        compact = self.candidates[0].compact()
        self.assertTrue(compact["image_verified"])
        self.assertEqual(compact["image_mime"], "image/jpeg")
        self.assertIsNotNone(compact["image_url"])
        without_image = make_candidate("cand_no_image", with_image=False, status="no_image").compact()
        self.assertIsNone(without_image["image_url"])
        self.assertFalse(without_image["image_verified"])
        self.assertIsNone(without_image["image_mime"])

    async def test_metadata_only_listing_returns_a_single_text_block(self):
        result = await server.present_reference_set(
            self.session.search_id, limit=3, attach_images=False
        )
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], str)
        payload = json.loads(result[0])
        self.assertTrue(payload["presentation"])
        for item in payload["presentation"]:
            self.assertIn("image_mime", item)
            self.assertIn("image_verified", item)

    async def test_images_are_attached_in_item_order(self):
        jpeg = _jpeg_bytes()
        with mock.patch.object(server, "fetch_image_bytes", new=_fake_fetch_factory(jpeg)):
            result = await server.present_reference_set(self.session.search_id, limit=3)
        payload = json.loads(result[0])
        items = payload["presentation"]
        self.assertEqual(len(result), 1 + 2 * len(items))
        for index, item in enumerate(items, start=1):
            label = result[2 * index - 1]
            self.assertIsInstance(label, str)
            self.assertEqual(
                label, f"{index}. {item['candidate_id']} | {item['title']} | {item['page_url']}"
            )
            block = result[2 * index]
            self.assertIsInstance(block, McpImage)
            self.assertEqual(block._format, "jpeg")
            Image.open(io.BytesIO(block.data)).load()

    async def test_one_failed_image_does_not_fail_the_call(self):
        with mock.patch.object(
            server, "fetch_image_bytes", new=_fake_fetch_factory(FetchError("Timed out fetching x"))
        ):
            result = await server.present_reference_set(self.session.search_id, limit=3)
        payload = json.loads(result[0])
        items = payload["presentation"]
        unavailable = [block for block in result[1:] if isinstance(block, str) and block.startswith("image_unavailable:")]
        self.assertEqual(len(unavailable), len(items))
        self.assertIn("Timed out fetching x", unavailable[0])
        self.assertEqual(result[1], f"1. {items[0]['candidate_id']} | {items[0]['title']} | {items[0]['page_url']}")
        self.assertTrue(all(item["image_url"] for item in items))

    async def test_vision_disabled_skips_attachment_with_a_note(self):
        config = server.get_config()
        server._config = type(config)(**{**config.__dict__, "vision": type(config.vision)(enabled=False)})
        with mock.patch.object(
            server, "fetch_image_bytes", new=_fake_fetch_factory(AssertionError("must not fetch"))
        ):
            result = await server.present_reference_set(self.session.search_id, limit=3)
        self.assertEqual(len(result), 1)
        payload = json.loads(result[0])
        self.assertTrue(payload["presentation"])
        self.assertTrue(any("vision is disabled" in note for note in payload["notes"]))


if __name__ == "__main__":
    unittest.main()
