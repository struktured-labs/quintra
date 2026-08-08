#!/usr/bin/env python3
"""Validate the static field archive against the current cartridge."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
VERSION = ROOT / "src/game/version.h"
SHOWCASE = ROOT / "docs/showcase"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_image(relative: str, size: tuple[int, int]) -> None:
    path = SHOWCASE / relative
    assert path.is_file(), f"missing showcase image: {relative}"
    with Image.open(path) as image:
        assert image.size == size, f"{relative} is {image.size}, expected {size}"


def main() -> None:
    data = json.loads((SHOWCASE / "manifest.json").read_text())
    version = re.search(r'QUINTRA_VERSION "([^"]+)"', VERSION.read_text()).group(1)
    assert data["meta"]["version"] == version, "showcase version is stale"
    assert data["meta"]["romSha256"] == sha256(ROM), "showcase ROM hash is stale"
    assert len(data["stages"]) == data["meta"]["stageCount"] == 9
    assert len(data["bosses"]) == data["meta"]["bossCount"] == 9
    assert len(data["monsters"]) == data["meta"]["monsterCount"] == 33
    assert [monster["id"] for monster in data["monsters"]] == list(range(33))
    assert len({monster["name"] for monster in data["monsters"]}) == 33

    for stage in data["stages"]:
        assert_image(stage["image"], (160, 144))
    for boss in data["bosses"]:
        assert_image(boss["image"], (160, 144))
    for monster in data["monsters"]:
        assert monster["stages"], f"{monster['name']} has no habitat"
        assert_image(monster["focus"], (128, 128))
        assert_image(monster["field"], (160, 144))
    assert_image(data["collages"]["stages"], (480, 504))
    assert_image(data["collages"]["monsters"], (768, 912))

    html = (SHOWCASE / "index.html").read_text()
    css = (SHOWCASE / "styles.css").read_text()
    js = (SHOWCASE / "app.js").read_text()
    assert "gallery-data.js" in html and "app.js" in html
    assert "http://" not in html + css + js and "https://" not in html + css + js, \
        "showcase must remain fully local"
    assert "data-view=\"stages\"" in html
    assert "data-view=\"bosses\"" in html
    assert "data-view=\"monsters\"" in html
    print(
        f"[showcase] PASS {version}, 9 stages, 9 Colossi, 33 monsters, "
        "local assets and ROM hash current"
    )


if __name__ == "__main__":
    main()
