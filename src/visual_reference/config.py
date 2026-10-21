"""Configuration loading.

One documented TOML file plus a few environment overrides. No secret is read here: the
search backend owns its own credentials.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG_PATHS = ("visual-reference.toml", "visual-reference.toml.example")


@dataclass(frozen=True)
class SearchConfig:
    candidate_limit: int = 30
    per_query_limit: int = 8
    page_fetch_limit: int = 10
    present_min: int = 3
    present_max: int = 5
    language: str = "es"


@dataclass(frozen=True)
class PiWebAccessConfig:
    enabled: bool = True
    server_path: str = ""
    command: str = "node"
    timeout_seconds: float = 90.0


@dataclass(frozen=True)
class VisionConfig:
    enabled: bool = True
    cache_analysis: bool = True
    max_image_edge: int = 1024
    max_image_bytes: int = 8_000_000


@dataclass(frozen=True)
class StorageConfig:
    database_path: str = "data/library.sqlite"


@dataclass(frozen=True)
class HttpConfig:
    timeout_seconds: float = 20.0
    max_response_bytes: int = 3_000_000
    max_redirects: int = 3
    user_agent: str = "visual-reference-engine/0.1 (+local MCP server)"


@dataclass(frozen=True)
class SelectionWeights:
    relevance: float = 0.35
    visual_quality: float = 0.25
    usefulness: float = 0.25
    novelty: float = 0.15

    def normalized(self) -> "SelectionWeights":
        total = self.relevance + self.visual_quality + self.usefulness + self.novelty
        if total <= 0:
            return SelectionWeights()
        return SelectionWeights(
            relevance=self.relevance / total,
            visual_quality=self.visual_quality / total,
            usefulness=self.usefulness / total,
            novelty=self.novelty / total,
        )


@dataclass(frozen=True)
class Config:
    search: SearchConfig = field(default_factory=SearchConfig)
    pi_web_access: PiWebAccessConfig = field(default_factory=PiWebAccessConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    http: HttpConfig = field(default_factory=HttpConfig)
    selection: SelectionWeights = field(default_factory=SelectionWeights)
    source_path: Path | None = None
    root: Path = field(default_factory=Path.cwd)


def _section(data: dict, name: str) -> dict:
    value = data.get(name)
    return value if isinstance(value, dict) else {}


def _build(section: dict, cls):
    fields = {f for f in cls.__dataclass_fields__}
    return cls(**{k: v for k, v in section.items() if k in fields})


def find_config_path(explicit: str | os.PathLike | None = None, root: Path | None = None) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.is_file() else None
    env_path = os.environ.get("VRE_CONFIG")
    if env_path:
        path = Path(env_path).expanduser()
        if path.is_file():
            return path
    base = Path(root or Path.cwd())
    for name in DEFAULT_CONFIG_PATHS:
        candidate = base / name
        if candidate.is_file():
            return candidate
    return None


def load_config(
    path: str | os.PathLike | None = None,
    root: Path | None = None,
    overrides: dict | None = None,
) -> Config:
    """Load configuration, then apply environment overrides.

    Missing configuration is valid: the defaults are the documented MVP defaults.
    """
    base_root = Path(root or Path.cwd()).resolve()
    config_path = find_config_path(path, base_root)
    data: dict = {}
    if config_path is not None:
        with config_path.open("rb") as handle:
            data = tomllib.load(handle)

    pi_cfg = _build(_section(data, "sources").get("pi_web_access", {}), PiWebAccessConfig)
    config = Config(
        search=_build(_section(data, "search"), SearchConfig),
        pi_web_access=pi_cfg,
        vision=_build(_section(data, "vision"), VisionConfig),
        storage=_build(_section(data, "storage"), StorageConfig),
        http=_build(_section(data, "http"), HttpConfig),
        selection=_build(_section(data, "selection"), SelectionWeights),
        source_path=config_path,
        root=base_root,
    )

    env_server = os.environ.get("VRE_PI_WEB_ACCESS_SERVER")
    env_db = os.environ.get("VRE_DB_PATH")
    env_root = os.environ.get("VRE_ROOT")
    if env_root:
        config = Config(**{**config.__dict__, "root": Path(env_root).expanduser().resolve()})
    if env_server:
        config = Config(**{**config.__dict__, "pi_web_access": PiWebAccessConfig(
            enabled=config.pi_web_access.enabled,
            server_path=env_server,
            command=config.pi_web_access.command,
            timeout_seconds=config.pi_web_access.timeout_seconds,
        )})
    if env_db:
        config = Config(**{**config.__dict__, "storage": StorageConfig(database_path=env_db)})
    if overrides:
        for key, value in overrides.items():
            if key in Config.__dataclass_fields__:
                config = Config(**{**config.__dict__, key: value})
    return config


def resolve_database_path(config: Config) -> Path:
    path = Path(config.storage.database_path).expanduser()
    if not path.is_absolute():
        path = config.root / path
    return path
