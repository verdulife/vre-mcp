"""Search sources. One module per source; several can be enabled at once."""

from __future__ import annotations

from ..config import Config
from .base import AdapterResult, SearchAdapter
from .pi_web_access import PiWebAccessAdapter


def build_adapters(config: Config) -> list[SearchAdapter]:
    adapters: list[SearchAdapter] = []
    if config.pi_web_access.enabled:
        adapters.append(PiWebAccessAdapter(config.pi_web_access))
    return adapters


__all__ = ["AdapterResult", "SearchAdapter", "PiWebAccessAdapter", "build_adapters"]
