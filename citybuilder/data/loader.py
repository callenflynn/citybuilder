"""Loader for city content definitions.

Reads JSON/TOML/YAML files from the content directory and returns validated,
plain-python dicts. Kept dependency-light so it works headless (no renderer).
"""

from __future__ import annotations

import json
import os
from typing import Any

try:
    import tomli  # type: ignore
except Exception:  # pragma: no cover - tomli only needed on py<3.11
    tomli = None

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional
    yaml = None


class ContentManager:
    def __init__(self, content_dir: str | None = None):
        if content_dir is None:
            # Default: <project>/citybuilder/data/citydefs
            here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            content_dir = os.path.join(here, "citydefs")
        self.content_dir = content_dir
        self.definitions: dict[str, dict[str, Any]] = {}

    def load_all(self) -> dict[str, dict[str, Any]]:
        self.definitions = {}
        if not os.path.isdir(self.content_dir):
            return self.definitions
        for category in sorted(os.listdir(self.content_dir)):
            cat_dir = os.path.join(self.content_dir, category)
            if not os.path.isdir(cat_dir):
                continue
            self.definitions[category] = {}
            for fname in sorted(os.listdir(cat_dir)):
                path = os.path.join(cat_dir, fname)
                if not os.path.isfile(path):
                    continue
                data = self._load_file(path)
                key = os.path.splitext(fname)[0]
                self.definitions[category][key] = data
        return self.definitions

    def get(self, category: str, key: str) -> dict[str, Any] | None:
        return self.definitions.get(category, {}).get(key)

    def _load_file(self, path: str) -> Any:
        ext = os.path.splitext(path)[1].lower()
        with open(path, "rb") as f:
            raw = f.read()
        if ext == ".json":
            return json.loads(raw.decode("utf-8"))
        if ext == ".toml":
            if tomli is None:
                raise RuntimeError("tomli is required to load .toml files")
            return tomli.loads(raw.decode("utf-8"))
        if ext in (".yaml", ".yml"):
            if yaml is None:
                raise RuntimeError("PyYAML is required to load .yaml files")
            return yaml.safe_load(raw)
        raise ValueError(f"unsupported content file type: {path}")
