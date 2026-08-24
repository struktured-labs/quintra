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


def assert_animation(relative: str, size: tuple[int, int], frames: int,
                     frame_ms: int = 120) -> None:
    path = SHOWCASE / relative
    assert path.is_file(), f"missing showcase animation: {relative}"
    with Image.open(path) as image:
        assert image.size == size, f"{relative} is {image.size}, expected {size}"
        # GIF encoders may merge two identical adjacent poses into one frame
        # with a doubled delay. The public contract is the synchronized
        # two-second encounter window, not redundant storage frames.
        durations = []
        for frame in range(image.n_frames):
            image.seek(frame)
            durations.append(image.info.get("duration", 0))
        assert image.n_frames >= 2 and sum(durations) == frames * frame_ms, (
            f"{relative} lasts {sum(durations)}ms across {image.n_frames} "
            f"frames, expected {frames * frame_ms}ms")


def assert_feature_portrait(relative: str) -> None:
    """Reject a crop containing only the patterned dungeon floor."""
    path = SHOWCASE / relative
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        border = set()
        for x in range(rgb.width):
            border.add(rgb.getpixel((x, 0)))
            border.add(rgb.getpixel((x, rgb.height - 1)))
        for y in range(rgb.height):
            border.add(rgb.getpixel((0, y)))
            border.add(rgb.getpixel((rgb.width - 1, y)))
        center = rgb.crop((32, 32, 96, 96))
        foreground = sum(pixel not in border for pixel in center.getdata())
        assert foreground >= 128, (
            f"{relative} contains no visible feature monster "
            f"({foreground} foreground pixels)")


def main() -> None:
    data = json.loads((SHOWCASE / "manifest.json").read_text())
    version = re.search(r'QUINTRA_VERSION "([^"]+)"', VERSION.read_text()).group(1)
    assert data["meta"]["version"] == version, "showcase version is stale"
    assert data["meta"]["romSha256"] == sha256(ROM), "showcase ROM hash is stale"
    assert len(data["stages"]) == data["meta"]["stageCount"] == 9
    assert len(data["bosses"]) == data["meta"]["bossCount"] == 9
    assert len(data["monsters"]) == data["meta"]["monsterCount"] == 35
    assert len(data["items"]) == data["meta"]["itemCount"] == 29
    assert [monster["id"] for monster in data["monsters"]] == list(range(35))
    assert len({monster["name"] for monster in data["monsters"]}) == 35

    for stage in data["stages"]:
        assert_image(stage["image"], (160, 144))
    for boss in data["bosses"]:
        assert_image(boss["image"], (160, 144))
        assert_animation(boss["animated"], (160, 144), 16)
    for monster in data["monsters"]:
        assert monster["stages"], f"{monster['name']} has no habitat"
        assert_image(monster["focus"], (128, 128))
        assert_image(monster["field"], (160, 144))
        if monster["id"] in (33, 34):
            assert_feature_portrait(monster["focus"])
    for item in data["items"]:
        assert_image(item["image"], (128, 128))
    assert_image(data["collages"]["stages"], (480, 504))
    assert_image(data["collages"]["monsters"], (768, 912))
    assert_image(data["collages"]["items"], (768, 760))
    assert_image(data["collages"]["worldAtlas"], (1600, 1884))

    html = (SHOWCASE / "index.html").read_text()
    css = (SHOWCASE / "styles.css").read_text()
    js = (SHOWCASE / "app.js").read_text()
    assert "gallery-data.js" in html and "app.js" in html
    assert "http://" not in html + css + js and "https://" not in html + css + js, \
        "showcase must remain fully local"
    assert "data-view=\"stages\"" in html
    assert "data-view=\"bosses\"" in html
    assert "data-view=\"monsters\"" in html
    assert "data-view=\"items\"" in html
    print(
        f"[showcase] PASS {version}, 9 stages, 9 Colossi, 35 monsters, 29 items, "
        "local assets and ROM hash current"
    )


if __name__ == "__main__":
    main()
