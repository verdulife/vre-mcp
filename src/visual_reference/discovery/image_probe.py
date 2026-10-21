"""Validate a remote image and derive cheap, comparable visual features.

The features exist so that set selection can favour genuinely different directions without
embeddings. They describe the file, not the design: never present them as an aesthetic
judgement.
"""

from __future__ import annotations

import io

import httpx
from PIL import Image, UnidentifiedImageError

from ..config import HttpConfig, VisionConfig
from ..http_safety import FetchError, fetch_image_bytes
from ..models import ImageInfo

THUMB_BACKGROUND = (255, 255, 255)


def _open_image(data: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise FetchError(f"The response is not a decodable image: {exc}") from exc
    return image


def visual_features(image: Image.Image) -> dict:
    """Dominant colours, mean brightness and aspect ratio from a decoded image."""
    rgb = image.convert("RGB")
    thumb = rgb.copy()
    thumb.thumbnail((48, 48))
    pixels = list(thumb.getdata())
    if not pixels:
        return {"dominant_colors": [], "brightness": None, "aspect_ratio": None}
    brightness = sum((0.299 * r + 0.587 * g + 0.114 * b) for r, g, b in pixels) / (len(pixels) * 255)
    quantized = thumb.quantize(colors=4, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette() or []
    counts = sorted(quantized.getcolors() or [], reverse=True)
    colors: list[str] = []
    for _count, index in counts[:3]:
        base = index * 3
        if base + 2 < len(palette):
            colors.append("#%02x%02x%02x" % (palette[base], palette[base + 1], palette[base + 2]))
    return {
        "dominant_colors": colors,
        "brightness": round(brightness, 3),
        "aspect_ratio": round(image.width / image.height, 3) if image.height else None,
    }


async def probe_image(
    url: str,
    http_config: HttpConfig,
    *,
    max_bytes: int | None = None,
    client: httpx.AsyncClient | None = None,
    discovery: str = "og:image",
) -> ImageInfo:
    """Fetch an image with the safety limits and return verified metadata."""
    resource = await fetch_image_bytes(url, http_config, max_bytes=max_bytes, client=client)
    image = _open_image(resource.content)
    features = visual_features(image)
    content_type = resource.content_type or f"image/{(image.format or 'unknown').lower()}"
    return ImageInfo(
        url=resource.final_url,
        width=image.width,
        height=image.height,
        content_type=content_type,
        byte_size=len(resource.content),
        discovery=discovery,
        verified=True,
        dominant_colors=features["dominant_colors"],
        brightness=features["brightness"],
        aspect_ratio=features["aspect_ratio"],
    )


def prepare_for_model(data: bytes, vision: VisionConfig) -> tuple[bytes, str]:
    """Downscale and normalize an image so it is cheap to hand to a model.

    Returns (bytes, mime_type). JPEG keeps token cost predictable; transparency is flattened.
    """
    limit = vision.max_image_bytes
    image = _open_image(data)
    if vision.max_image_edge and max(image.width, image.height) > vision.max_image_edge:
        image.thumbnail((vision.max_image_edge, vision.max_image_edge), Image.Resampling.LANCZOS)
    if image.mode in {"RGBA", "LA", "P"}:
        background = Image.new("RGB", image.size, THUMB_BACKGROUND)
        rgba = image.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1])
        image = background
    else:
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=82, optimize=True)
    out = buffer.getvalue()
    if len(out) > limit:
        # one more pass at lower quality before refusing
        image.thumbnail((max(320, image.width // 2), max(320, image.height // 2)), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=70, optimize=True)
        out = buffer.getvalue()
    if len(out) > limit:
        raise FetchError("The image is too large to hand to the model after downscaling.")
    return out, "image/jpeg"
