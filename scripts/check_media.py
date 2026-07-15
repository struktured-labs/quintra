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
VERSION = ROOT / "src/game/version.h"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    meta = json.loads(META.read_text())
    match = re.search(r'QUINTRA_VERSION\s+"([^"]+)"', VERSION.read_text())
    assert match, "missing cartridge version"
    assert meta["version"] == match.group(1), "gameplay reel version is stale"
    assert meta["rom_sha256"] == sha256(ROM), "gameplay reel ROM hash is stale"
    assert meta["capture_sha256"] == sha256(CAPTURE), "capture recipe changed"
    assert meta["gif_sha256"] == sha256(GIF), "gameplay GIF changed without metadata"
    assert GIF.stat().st_size <= 256 * 1024, "gameplay GIF exceeds 256 KiB"

    with Image.open(GIF) as image:
        assert image.size == (meta["width"], meta["height"])
        assert image.n_frames == meta["frames"]
        for frame in range(image.n_frames):
            image.seek(frame)
            assert image.info.get("duration") == meta["frame_ms"], (
                f"gameplay frame {frame} duration drifted"
            )
    print(f"[media] PASS {meta['version']} {meta['frames']} frames, "
          f"{GIF.stat().st_size} bytes, ROM/reel/recipe hashes current")


if __name__ == "__main__":
    main()
