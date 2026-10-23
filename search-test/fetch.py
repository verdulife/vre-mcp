"""Disposable probe: page URL -> real image file.

Fetch a candidate page, take the image it declares (og:image / twitter:image / image_src /
largest inline image), download the bytes, validate them with Pillow and keep up to N.
No browser, no API, no state. Delete this folder when the measurement is done.
"""

from __future__ import annotations

import hashlib
import json
import re
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from PIL import Image

OUT = Path(__file__).resolve().parent
WANTED = 5
MAX_PER_PAGE = 1  # one image per project: five images must mean five different projects
MIN_SHORT_EDGE = 600
MIN_AREA = 300_000
MAX_BYTES = 12_000_000
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

PAGES = [
    ("overmind.design", "https://overmind.design/DISCO-FUTURISTA-1989"),
    ("fontsinuse.com", "https://fontsinuse.com/uses/26269/forms-at-fabric-poster-series-2019"),
    ("vasa.works", "https://inspiration.vasa.works/item/branding/31257698314c82dc721de680f7944b9b"),
    ("dribbble.com", "https://dribbble.com/shots/2459008-Typography-Music-Event-Party-Flyers-2"),
    ("dribbble.com", "https://dribbble.com/shots/1905950-80s-Night"),
    ("dribbble.com", "https://dribbble.com/shots/25359103-Ladies-Night-club-poster-design"),
    ("andrealiang.com", "https://andrealiang.com/poster-design-silent-disco-event"),
    ("otaviosantiago.com", "https://www.otaviosantiago.com/berghain"),
    ("behance.net", "https://www.behance.net/gallery/191202029/TECHNO-SYNCHRO"),
    ("behance.net", "https://www.behance.net/gallery/86233799/RAVE-CLUB-Poster-series"),
    ("chkdesign.com", "https://chkdesign.com/work/disco-freaks"),
]


def declared_images(soup: BeautifulSoup, page_url: str) -> list[str]:
    """Images the page itself declares, in priority order."""
    found: list[str] = []
    for prop in ("og:image", "og:image:secure_url", "twitter:image"):
        for tag in soup.find_all("meta", attrs={"property": prop}) + soup.find_all(
            "meta", attrs={"name": prop}
        ):
            if tag.get("content"):
                found.append(tag["content"])
    for tag in soup.find_all("link", attrs={"rel": "image_src"}):
        if tag.get("href"):
            found.append(tag["href"])
    # Largest inline image as a fallback: width attribute first, then any CDN-looking src.
    inline: list[tuple[int, str]] = []
    for tag in soup.find_all("img"):
        src = tag.get("src") or tag.get("data-src") or ""
        if not src or src.startswith("data:"):
            continue
        width = tag.get("width") or "0"
        try:
            weight = int(re.sub(r"\D", "", str(width)) or 0)
        except ValueError:
            weight = 0
        if re.search(r"\.(jpe?g|png|webp)", src, re.I):
            inline.append((weight, src))
    inline.sort(reverse=True)
    found.extend(src for _, src in inline[:4])
    resolved: list[str] = []
    for url in found:
        absolute = urljoin(page_url, url.strip())
        if absolute.startswith(("http://", "https://")) and absolute not in resolved:
            resolved.append(absolute)
    return resolved


def validate(data: bytes) -> tuple[bool, dict]:
    try:
        with Image.open(BytesIO(data)) as image:
            image.load()
            width, height = image.size
            return (
                min(width, height) >= MIN_SHORT_EDGE and width * height >= MIN_AREA,
                {"width": width, "height": height, "format": image.format},
            )
    except Exception as exc:  # noqa: BLE001 - a probe reports, it does not crash
        return False, {"error": f"{type(exc).__name__}: {exc}"}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def main() -> int:
    report: list[dict] = []
    kept: list[dict] = []
    seen_hashes: set[str] = set()

    with httpx.Client(
        follow_redirects=True,
        timeout=20.0,
        headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"},
    ) as client:
        for source, page_url in PAGES:
            if len(kept) >= WANTED:
                break
            entry: dict = {"source": source, "page": page_url}
            try:
                page = client.get(page_url)
                entry["page_status"] = page.status_code
                if page.status_code != 200:
                    entry["result"] = "page-rejected"
                    report.append(entry)
                    continue
                soup = BeautifulSoup(page.text, "html.parser")
                candidates = declared_images(soup, page_url)
                entry["declared_images"] = len(candidates)
                if not candidates:
                    entry["result"] = "no-image-declared"
                    report.append(entry)
                    continue

                kept_here = 0
                for image_url in candidates[:3]:
                    if len(kept) >= WANTED or kept_here >= MAX_PER_PAGE:
                        break
                    try:
                        response = client.get(image_url)
                    except httpx.HTTPError as exc:
                        entry.setdefault("image_errors", []).append(f"{image_url} -> {exc}")
                        continue
                    if response.status_code != 200:
                        entry.setdefault("image_errors", []).append(
                            f"{image_url} -> HTTP {response.status_code}"
                        )
                        continue
                    data = response.content
                    if len(data) > MAX_BYTES:
                        entry.setdefault("image_errors", []).append(f"{image_url} -> too large")
                        continue
                    digest = hashlib.sha256(data).hexdigest()
                    if digest in seen_hashes:
                        entry.setdefault("image_errors", []).append(f"{image_url} -> duplicate")
                        continue
                    ok, meta = validate(data)
                    if not ok:
                        entry.setdefault("image_errors", []).append(
                            f"{image_url} -> rejected {meta}"
                        )
                        continue
                    seen_hashes.add(digest)
                    kept_here += 1
                    extension = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}.get(
                        meta["format"] or "", "jpg"
                    )
                    name = f"{len(kept) + 1:02d}-{slug(source)}-{slug(urlparse(page_url).path.split('/')[-1])}.{extension}"
                    (OUT / name).write_bytes(data)
                    kept.append(
                        {
                            "file": name,
                            "source": source,
                            "page": page_url,
                            "image_url": image_url,
                            "width": meta["width"],
                            "height": meta["height"],
                            "format": meta["format"],
                            "bytes": len(data),
                        }
                    )
                entry["result"] = "used" if kept_here else "no-usable-image"
            except Exception as exc:  # noqa: BLE001
                entry["result"] = f"error {type(exc).__name__}: {exc}"
            report.append(entry)

    (OUT / "manifest.json").write_text(
        json.dumps({"wanted": WANTED, "kept": kept, "pages": report}, indent=2),
        encoding="utf-8",
    )
    print(f"kept {len(kept)}/{WANTED}")
    for item in kept:
        print(f"  {item['file']}  {item['width']}x{item['height']}  {item['bytes'] // 1024} KB  {item['source']}")
    print("\nper page:")
    for entry in report:
        print(f"  {entry['source']:<20} {entry.get('result')}")
    return 0 if len(kept) >= WANTED else 1


if __name__ == "__main__":
    raise SystemExit(main())
