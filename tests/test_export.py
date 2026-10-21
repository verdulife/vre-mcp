"""`save_reference_images`: the explicit opt-in that writes real image files locally."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mcp.server.fastmcp.exceptions import ToolError
from PIL import Image

from tests.fixtures import make_candidate
from vre import server
from vre.http_safety import FetchError, FetchedResource
from vre.models import SearchOutcome

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _image_bytes(width: int = 640, height: int = 400, fmt: str = "JPEG") -> bytes:
    """A real, decodable image generated locally; no network involved."""
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (210, 80, 60)).save(buffer, format=fmt)
    return buffer.getvalue()


def _fetch_map(mapping: dict[str, bytes | Exception]):
    async def fake_fetch(url: str, config, *, max_bytes=None, client=None):
        payload = mapping[url]
        if isinstance(payload, Exception):
            raise payload
        mime = "image/png" if payload.startswith(PNG_MAGIC) else "image/jpeg"
        return FetchedResource(
            url=url, final_url=url, status_code=200, content_type=mime, content=payload
        )

    return fake_fetch


def _isolated_environment(testcase):
    tmp = tempfile.TemporaryDirectory()
    testcase.addCleanup(tmp.cleanup)
    root = Path(tmp.name).resolve()
    patcher = mock.patch.dict(
        os.environ,
        {"VRE_DB_PATH": str(root / "library.sqlite"), "VRE_ROOT": str(root)},
    )
    patcher.start()
    testcase.addCleanup(patcher.stop)
    server.reset_state()
    testcase.addCleanup(server.reset_state)
    return root


class SaveReferenceImagesTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.root = _isolated_environment(self)
        self.jpeg = _image_bytes(640, 400, "JPEG")
        self.png = _image_bytes(300, 500, "PNG")
        self.candidates = [
            make_candidate(
                "cand_a", "https://example.test/cand_a", title="Festival poster full bleed"
            ),
            make_candidate(
                "cand_b", "https://example.test/cand_b", title="Risograph texture study"
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
        self.mapping = {
            self.candidates[0].image_url: self.jpeg,
            self.candidates[1].image_url: self.png,
        }

    def _references_dir(self, folder: str = "posters") -> Path:
        return self.root / "data" / "references" / folder

    async def test_saves_files_dimensions_and_index(self):
        with mock.patch.object(server, "fetch_image_bytes", new=_fetch_map(self.mapping)):
            payload = json.loads(
                await server.save_reference_images(
                    candidate_ids=["cand_a", "cand_b"], folder="posters"
                )
            )

        folder = self._references_dir()
        self.assertEqual(payload["folder"], str(folder))
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["errors"], [])
        self.assertIn("copies of the original images", payload["note"])

        for index, entry in enumerate(payload["saved"], start=1):
            path = Path(entry["file"])
            self.assertTrue(path.is_absolute())
            self.assertTrue(path.is_file())
            self.assertEqual(path.parent, folder)
            self.assertTrue(path.name.startswith(f"{index:02d}-"))
            with Image.open(path) as image:
                self.assertEqual(image.size, (entry["width"], entry["height"]))

        self.assertEqual(
            [(entry["width"], entry["height"]) for entry in payload["saved"]],
            [(640, 400), (300, 500)],
        )
        self.assertTrue(payload["saved"][0]["file"].endswith(".jpg"))
        self.assertTrue(payload["saved"][1]["file"].endswith(".png"))

        index = json.loads((folder / "index.json").read_text(encoding="utf-8"))
        self.assertTrue(index["updated_at"])
        self.assertEqual(len(index["references"]), 2)
        for stored in index["references"]:
            self.assertEqual(
                set(stored),
                {
                    "file",
                    "image_url",
                    "page_url",
                    "title",
                    "width",
                    "height",
                    "bytes",
                    "saved_at",
                },
            )
        self.assertEqual(
            {stored["image_url"] for stored in index["references"]},
            set(self.mapping),
        )

    async def test_second_save_never_overwrites_and_keeps_index_unique(self):
        with mock.patch.object(server, "fetch_image_bytes", new=_fetch_map(self.mapping)):
            first = json.loads(
                await server.save_reference_images(candidate_ids=["cand_a"], folder="posters")
            )
            second = json.loads(
                await server.save_reference_images(candidate_ids=["cand_a"], folder="posters")
            )

        first_file = Path(first["saved"][0]["file"])
        second_file = Path(second["saved"][0]["file"])
        self.assertNotEqual(first_file, second_file)
        self.assertTrue(first_file.is_file())
        self.assertTrue(second_file.is_file())
        self.assertTrue(second_file.name.endswith("-2.jpg"))

        index = json.loads((self._references_dir() / "index.json").read_text(encoding="utf-8"))
        urls = [stored["image_url"] for stored in index["references"]]
        self.assertEqual(len(urls), len(set(urls)))
        self.assertEqual(urls, [self.candidates[0].image_url])

    async def test_unsafe_folders_are_rejected(self):
        for folder in ("../evil", "/abs", "a/b", "bad name!", "", ".", ".."):
            with self.subTest(folder=folder):
                with self.assertRaises(ToolError):
                    await server.save_reference_images(candidate_ids=["cand_a"], folder=folder)
        self.assertFalse((self.root / "data" / "evil").exists())

    async def test_safe_helper_rejects_and_accepts_segments(self):
        self.assertEqual(server._safe_folder_name("posters-2026_v1"), "posters-2026_v1")
        for folder in ("../evil", "/abs", "a/b", "bad name!", "", "."):
            with self.subTest(folder=folder):
                with self.assertRaises(ToolError):
                    server._safe_folder_name(folder)

    async def test_unknown_id_is_rejected(self):
        with self.assertRaises(ToolError) as caught:
            await server.save_reference_images(candidate_ids=["cand_a", "cand_missing"])
        self.assertIn("cand_missing", str(caught.exception))
        self.assertFalse((self.root / "data" / "references").exists())

        with self.assertRaises(ToolError) as caught:
            await server.save_reference_images(reference_ids=["ref_missing"])
        self.assertIn("ref_missing", str(caught.exception))

    async def test_empty_request_is_rejected(self):
        with self.assertRaises(ToolError):
            await server.save_reference_images()
        with self.assertRaises(ToolError):
            await server.save_reference_images(candidate_ids=[], reference_ids=[])

    async def test_one_failed_image_does_not_abort_the_others(self):
        mapping = dict(self.mapping)
        mapping[self.candidates[1].image_url] = FetchError("Timed out fetching image")
        with mock.patch.object(server, "fetch_image_bytes", new=_fetch_map(mapping)):
            payload = json.loads(
                await server.save_reference_images(
                    candidate_ids=["cand_a", "cand_b"], folder="posters"
                )
            )
        self.assertEqual(payload["count"], 1)
        self.assertEqual(len(payload["saved"]), 1)
        self.assertTrue(Path(payload["saved"][0]["file"]).is_file())
        self.assertEqual(len(payload["errors"]), 1)
        self.assertEqual(payload["errors"][0]["id"], "cand_b")
        self.assertIn("Timed out fetching image", payload["errors"][0]["error"])
        index = json.loads((self._references_dir() / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(len(index["references"]), 1)

    async def test_undecodable_bytes_are_reported_per_item(self):
        mapping = {self.candidates[0].image_url: b"not an image"}
        with mock.patch.object(server, "fetch_image_bytes", new=_fetch_map(mapping)):
            payload = json.loads(
                await server.save_reference_images(candidate_ids=["cand_a"], folder="posters")
            )
        self.assertEqual(payload["count"], 0)
        self.assertEqual(payload["errors"][0]["id"], "cand_a")

    async def test_saving_by_reference_id_works(self):
        with mock.patch.object(server, "fetch_image_bytes", new=_fetch_map(self.mapping)):
            stored = json.loads(
                await server.save_references(project_name="Poster study", candidate_ids=["cand_a"])
            )
            reference_id = stored["saved"][0]["reference_id"]
            payload = json.loads(
                await server.save_reference_images(reference_ids=[reference_id], folder="posters")
            )
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["saved"][0]["image_url"], self.candidates[0].image_url)
        self.assertTrue(Path(payload["saved"][0]["file"]).is_file())

    async def test_default_folder_is_the_project_slug(self):
        project = server.get_repository().create_project("Sitges Brutalist Poster!")
        self.session.project_id = project["id"]
        with mock.patch.object(server, "fetch_image_bytes", new=_fetch_map(self.mapping)):
            payload = json.loads(await server.save_reference_images(candidate_ids=["cand_a"]))
        self.assertEqual(
            payload["folder"], str(self.root / "data" / "references" / "sitges-brutalist-poster")
        )
        self.assertTrue(Path(payload["saved"][0]["file"]).is_file())

    async def test_default_folder_without_project_is_references(self):
        with mock.patch.object(server, "fetch_image_bytes", new=_fetch_map(self.mapping)):
            payload = json.loads(await server.save_reference_images(candidate_ids=["cand_a"]))
        self.assertEqual(payload["folder"], str(self.root / "data" / "references" / "references"))


if __name__ == "__main__":
    unittest.main()
