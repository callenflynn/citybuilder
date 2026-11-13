"""Tests for the content data loader."""

import os
import tempfile
from citybuilder.data.loader import ContentManager


def test_loads_json_definitions():
    with tempfile.TemporaryDirectory() as d:
        cat = os.path.join(d, "buildings")
        os.makedirs(cat)
        with open(os.path.join(cat, "house.json"), "w") as f:
            f.write('{"name": "house", "levels": 2}')
        cm = ContentManager(d)
        cm.load_all()
        assert cm.get("buildings", "house") == {"name": "house", "levels": 2}


def test_missing_dir_is_empty():
    cm = ContentManager("/nonexistent/path/xyz")
    assert cm.load_all() == {}
