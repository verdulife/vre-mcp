"""Image discovery inside a result page.

Only the page's own declared visual resources are used (Open Graph, Twitter card,
`link rel=image_src`, JSON-LD, then the first plausible `<img>`). Nothing is guessed and
nothing is fabricated: when no image is found the candidate is reported without one.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from ..urls import absolute_url

MAX_IMG_CANDIDATES = 6
MIN_IMG_EDGE = 200


@dataclass
class ImageReference:
    url: str
    discovery: str
    width: int | None = None
    height: int | None = None


def _int_or_none(value) -> int | None:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _jsonld_images(soup: BeautifulSoup, base_url: str) -> list[ImageReference]:
    found: list[ImageReference] = []
    for script in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        raw = script.string or script.get_text() or ""
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                for key, value in node.items():
                    if key in {"image", "thumbnailUrl", "primaryImageOfPage"}:
                        if isinstance(value, str):
                            url = absolute_url(base_url, value)
                            if url:
                                found.append(ImageReference(url, "json-ld"))
                        elif isinstance(value, dict):
                            url = absolute_url(base_url, str(value.get("url") or value.get("contentUrl") or ""))
                            if url:
                                found.append(
                                    ImageReference(
                                        url,
                                        "json-ld",
                                        _int_or_none(value.get("width")),
                                        _int_or_none(value.get("height")),
                                    )
                                )
                        elif isinstance(value, list):
                            stack.extend(value)
                    elif isinstance(value, (dict, list)):
                        stack.append(value)
    return found


def extract_image_candidates(html: str, base_url: str) -> list[ImageReference]:
    """Return declared image candidates in priority order, without duplicates."""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[ImageReference] = []

    def add(url: str | None, discovery: str, width=None, height=None) -> None:
        if not url:
            return
        if any(existing.url == url for existing in candidates):
            return
        candidates.append(ImageReference(url, discovery, _int_or_none(width), _int_or_none(height)))

    def meta(name: str) -> list:
        return soup.find_all("meta", attrs={"property": name}) + soup.find_all("meta", attrs={"name": name})

    for tag in meta("og:image:secure_url"):
        add(absolute_url(base_url, tag.get("content", "")), "og:image")
    for tag in meta("og:image"):
        add(absolute_url(base_url, tag.get("content", "")), "og:image")
    og_widths = [tag.get("content") for tag in meta("og:image:width")]
    og_heights = [tag.get("content") for tag in meta("og:image:height")]
    if candidates and candidates[0].discovery == "og:image":
        candidates[0].width = _int_or_none(og_widths[0]) if og_widths else None
        candidates[0].height = _int_or_none(og_heights[0]) if og_heights else None

    for tag in meta("twitter:image") + meta("twitter:image:src"):
        add(absolute_url(base_url, tag.get("content", "")), "twitter:image")

    for tag in soup.find_all("link", attrs={"rel": re.compile("image_src", re.I)}):
        add(absolute_url(base_url, tag.get("href", "")), "link:image_src")

    if not candidates:
        for reference in _jsonld_images(soup, base_url):
            add(reference.url, reference.discovery, reference.width, reference.height)

    if not candidates:
        for tag in soup.find_all("img"):
            src = tag.get("src") or tag.get("data-src") or tag.get("data-original")
            url = absolute_url(base_url, src or "")
            if not url:
                continue
            width = _int_or_none(tag.get("width"))
            height = _int_or_none(tag.get("height"))
            # A declared size is markup, not a measurement: it is only trusted to reject site
            # chrome, and never recorded as the candidate's width/height (only probing the
            # file verifies dimensions).
            tiny = (width is not None and width < MIN_IMG_EDGE) or (
                height is not None and height < MIN_IMG_EDGE
            )
            if tiny:
                continue
            add(url, "img")
            if len(candidates) >= MAX_IMG_CANDIDATES:
                break

    return candidates[:MAX_IMG_CANDIDATES]
