"""Image discovery precedence and SSRF-safe fetching (spec §11, §12, §17)."""

from __future__ import annotations

import unittest

from visual_reference.discovery.image_extract import extract_image_candidates

PAGE = """<html><head>
<meta property="og:image" content="/media/poster.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="800">
<meta name="twitter:image" content="https://cdn.test/twitter.jpg">
<link rel="image_src" href="https://cdn.test/link.jpg">
</head><body><img src="/body.jpg" width="900" height="600"></body></html>"""

PAGE_NO_META = """<html><body>
<img src="/logo.png" width="40" height="40">
<img src="/works/01.jpg" width="900" height="600">
</body></html>"""

PAGE_JSONLD = """<html><head><script type="application/ld+json">
{"@type":"CreativeWork","image":{"url":"https://cdn.test/work.png","width":1000,"height":1000}}
</script></head><body></body></html>"""


class ImageExtractionTests(unittest.TestCase):
    def test_og_image_wins_and_relative_urls_resolve(self):
        candidates = extract_image_candidates(PAGE, "https://example.test/post/1")
        self.assertEqual(candidates[0].url, "https://example.test/media/poster.jpg")
        self.assertEqual(candidates[0].discovery, "og:image")
        self.assertEqual((candidates[0].width, candidates[0].height), (1200, 800))
        self.assertIn("https://cdn.test/twitter.jpg", [item.url for item in candidates])

    def test_json_ld_used_when_no_social_meta(self):
        candidates = extract_image_candidates(PAGE_JSONLD, "https://example.test/post")
        self.assertEqual(candidates[0].url, "https://cdn.test/work.png")
        self.assertEqual(candidates[0].discovery, "json-ld")
        self.assertEqual(candidates[0].width, 1000)

    def test_body_images_fail_over_without_inventing_metadata(self):
        candidates = extract_image_candidates(PAGE_NO_META, "https://example.test/post")
        urls = [item.url for item in candidates]
        self.assertIn("https://example.test/works/01.jpg", urls)
        self.assertEqual(candidates[0].discovery, "img")
        self.assertIsNone(candidates[0].width)

    def test_page_without_images_returns_empty(self):
        self.assertEqual(extract_image_candidates("<html><body><p>text</p></body></html>", "https://a.test"), [])

    def test_data_uris_are_refused(self):
        page = '<html><head><meta property="og:image" content="data:image/png;base64,AAAA"></head></html>'
        self.assertEqual(extract_image_candidates(page, "https://a.test"), [])


class NoiseFilterTests(unittest.TestCase):
    def test_site_chrome_is_matched(self):
        from visual_reference.discovery.orchestrator import NOISE_URL_RE

        for url in (
            "https://designlenta.ru/images/logo.png",
            "https://a.test/favicon.ico",
            "https://a.test/img/placeholder-image.jpg",
            "https://a.test/pixel.gif",
        ):
            self.assertIsNotNone(NOISE_URL_RE.search(url), url)
        for url in (
            "https://a.test/works/poster-2024.jpg",
            "https://a.test/uploads/logo-experiment-poster.jpg",
        ):
            self.assertIsNone(NOISE_URL_RE.search(url), url)


if __name__ == "__main__":
    unittest.main()
