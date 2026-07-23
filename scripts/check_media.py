#!/usr/bin/env python3
"""Validate that the conference-facing gameplay reel matches this ROM."""
import hashlib
import json
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
GIF = ROOT / "docs/media/gameplay.gif"
META = ROOT / "docs/media/gameplay.json"
CAPTURE = ROOT / "scripts/capture_media.lua"
TITLE = ROOT / "docs/media/title.png"
TITLE_CAPTURE = ROOT / "scripts/capture_title_media.py"
BOSS_GALLERY = ROOT / "docs/media/boss-gallery.png"
BOSS_GALLERY_GIF = ROOT / "docs/media/boss-gallery.gif"
BOSS_GALLERY_CAPTURE = ROOT / "scripts/capture_boss_gallery.py"
VERSION = ROOT / "src/game/version.h"
STILLS = tuple(ROOT / "docs/media" / name for name in (
    "boss.png", "class.png", "class_preview.png", "compass.png",
    "dungeon.png", "ember.png", "pack.png", "riftwild-map.png",
    "sanctuary.png", "shop.png", "village.png",
))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_concat(paths):
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main():
    meta = json.loads(META.read_text())
    match = re.search(r'QUINTRA_VERSION\s+"([^"]+)"', VERSION.read_text())
    assert match, "missing cartridge version"
    assert meta["version"] == match.group(1), "gameplay reel version is stale"
    assert meta["rom_sha256"] == sha256(ROM), "gameplay reel ROM hash is stale"
    assert meta["capture_sha256"] == sha256(CAPTURE), "capture recipe changed"
    assert meta["gif_sha256"] == sha256(GIF), "gameplay GIF changed without metadata"
    assert meta["title_sha256"] == sha256(TITLE), "README title image is stale"
    assert meta["title_capture_sha256"] == sha256(TITLE_CAPTURE), "title capture recipe changed"
    assert meta["boss_gallery_sha256"] == sha256(BOSS_GALLERY), \
        "README boss gallery is stale"
    assert meta["boss_gallery_gif_sha256"] == sha256(BOSS_GALLERY_GIF), \
        "README animated boss gallery is stale"
    assert meta["boss_gallery_capture_sha256"] == sha256(BOSS_GALLERY_CAPTURE), \
        "boss gallery capture recipe changed"
    assert meta["stills_sha256"] == sha256_concat(STILLS), \
        "README still gallery is stale"
    assert GIF.stat().st_size <= 256 * 1024, "gameplay GIF exceeds 256 KiB"

    with Image.open(GIF) as image:
        assert image.size == (meta["width"], meta["height"])
        assert image.n_frames == meta["frames"]
        for frame in range(image.n_frames):
            image.seek(frame)
            assert image.info.get("duration") == meta["frame_ms"], (
                f"gameplay frame {frame} duration drifted"
            )
    with Image.open(TITLE) as image:
        assert image.size == (160, 144), "README title image has wrong dimensions"
    with Image.open(BOSS_GALLERY) as image:
        assert image.size == (480, 480), "README boss gallery has wrong dimensions"
    assert BOSS_GALLERY_GIF.stat().st_size <= 2 * 1024 * 1024, \
        "animated boss gallery exceeds 2 MiB"
    with Image.open(BOSS_GALLERY_GIF) as image:
        assert image.size == (480, 480), \
            "README animated boss gallery has wrong dimensions"
        assert image.n_frames == meta["boss_gallery_frames"]
        panel_hashes = [set() for _ in range(9)]
        for frame in range(image.n_frames):
            image.seek(frame)
            assert image.info.get("duration") == meta["boss_gallery_frame_ms"], (
                f"boss gallery frame {frame} duration drifted"
            )
            rgb = image.convert("RGB")
            for panel in range(9):
                x = (panel % 3) * 160
                y = (panel // 3) * 160
                panel_hashes[panel].add(hashlib.sha256(
                    rgb.crop((x, y, x + 160, y + 144)).tobytes()
                ).hexdigest())
        assert all(len(hashes) >= 2 for hashes in panel_hashes), (
            "animated boss gallery contains a static encounter panel: "
            f"{[len(hashes) for hashes in panel_hashes]}"
        )
    for still in STILLS:
        with Image.open(still) as image:
            assert image.size == (160, 144), \
                f"README still has wrong dimensions: {still.name}"
    print(f"[media] PASS {meta['version']} {meta['frames']} frames, "
          f"{GIF.stat().st_size} bytes, ROM/reel/recipe hashes current")


if __name__ == "__main__":
    main()
