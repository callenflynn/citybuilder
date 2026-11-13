"""Save/load: one folder per city, chunked, expandable, versioned migrations.

Stub for M1.5.
"""

from __future__ import annotations

import json
import os

MANIFEST_FILE = "manifest.json"
FORMAT_VERSION = 1


def city_path(saves_dir: str, city_name: str) -> str:
    return os.path.join(saves_dir, city_name)


def manifest_path(city_dir: str) -> str:
    return os.path.join(city_dir, MANIFEST_FILE)


def create_city(saves_dir: str, city_name: str, seed: int, map_size: int) -> str:
    """Initialize a new city save folder. Returns the city directory."""
    city_dir = city_path(saves_dir, city_name)
    os.makedirs(city_dir, exist_ok=True)
    manifest = {
        "format_version": FORMAT_VERSION,
        "city_name": city_name,
        "seed": int(seed),
        "map_size": int(map_size),
    }
    with open(manifest_path(city_dir), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return city_dir


def load_manifest(city_dir: str) -> dict:
    with open(manifest_path(city_dir), "r", encoding="utf-8") as f:
        return json.load(f)
