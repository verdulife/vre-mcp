"""SSRF protection and bounded fetching (spec §12, §17).

Network-free: the HTTP layer is exercised through httpx.MockTransport, so the tests prove the
policy logic itself instead of depending on the internet.
"""

from __future__ import annotations

import unittest

import httpx

from visual_reference.config import HttpConfig
from visual_reference.http_safety import (
    BlockedURLError,
    FetchError,
    assert_public_http_url,
    fetch_resource,
)

PUBLIC_IP = "93.184.216.34"


class UrlPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def test_private_and_loopback_targets_are_refused(self):
        for url in (
            "https://127.0.0.1/secret",
            "http://localhost:8080/x",
            "http://169.254.169.254/latest/meta-data/",
            "http://10.1.2.3/x",
            "http://[::1]/x",
        ):
            with self.assertRaises(BlockedURLError, msg=url):
                await assert_public_http_url(url)

    async def test_non_http_schemes_are_refused(self):
        for url in ("file:///C:/Windows/win.ini", "ftp://a.test/x", "javascript:alert(1)"):
            with self.assertRaises(BlockedURLError, msg=url):
                await assert_public_http_url(url)

    async def test_literal_public_address_is_allowed(self):
        await assert_public_http_url(f"https://{PUBLIC_IP}/image.jpg")

    async def test_unresolvable_host_reports_a_fetch_error(self):
        with self.assertRaises(FetchError):
            await assert_public_http_url("https://this-host-should-not-exist.invalid/x")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)


class BoundedFetchTests(unittest.IsolatedAsyncioTestCase):
    async def test_response_is_truncated_at_the_byte_cap(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=b"x" * 1000)

        async with _client(handler) as client:
            resource = await fetch_resource(
                f"https://{PUBLIC_IP}/image.jpg", HttpConfig(max_response_bytes=100), client=client
            )
        self.assertTrue(resource.truncated)
        self.assertEqual(len(resource.content), 100)
        self.assertEqual(resource.content_type, "image/jpeg")

    async def test_redirect_to_a_private_address_is_refused(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == PUBLIC_IP:
                return httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})
            return httpx.Response(200, content=b"secret")

        async with _client(handler) as client:
            with self.assertRaises(BlockedURLError):
                await fetch_resource(f"https://{PUBLIC_IP}/redirect", HttpConfig(), client=client)

    async def test_too_many_redirects_is_reported(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"location": f"https://{PUBLIC_IP}/again"})

        async with _client(handler) as client:
            with self.assertRaises(FetchError) as caught:
                await fetch_resource(f"https://{PUBLIC_IP}/loop", HttpConfig(max_redirects=2), client=client)
        self.assertIn("redirect", str(caught.exception).lower())

    async def test_error_status_is_reported_as_failure(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, content=b"not found")

        async with _client(handler) as client:
            with self.assertRaises(FetchError) as caught:
                await fetch_resource(f"https://{PUBLIC_IP}/missing", HttpConfig(), client=client)
        self.assertIn("404", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
