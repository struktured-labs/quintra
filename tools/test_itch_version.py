#!/usr/bin/env python3
"""Check manual and tag-driven package versions without publishing."""
import json
import os
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent.parent
BUILDER = ROOT / "tools/build_itch_web.sh"


def build(version):
    env = dict(os.environ)
    env.pop("QUINTRA_WEB_VERSION", None)
    if version is not None:
        env["QUINTRA_WEB_VERSION"] = version
    return subprocess.run([str(BUILDER)], env=env, capture_output=True, text=True)


def check(version):
    result = build(version)
    assert result.returncode == 0, result.stdout + result.stderr
    metadata = json.loads((ROOT / "builds/itch-web/build.json").read_text())
    expected = version or "v0.20.19-beta27"
    assert metadata["version"] == expected, metadata
    with zipfile.ZipFile(ROOT / f"builds/quintra-itch-web-{expected}.zip") as archive:
        assert json.loads(archive.read("build.json"))["version"] == expected
        assert f"quintra-player.js?v={expected}" in archive.read("index.html").decode()


if __name__ == "__main__":
    try:
        check("v0.20.20")
        before = (ROOT / "builds/itch-web/build.json").read_bytes()
        for invalid in ("../escape", "v1.2.3/escape", "v1.2.3\nextra"):
            result = build(invalid)
            assert result.returncode != 0 and "Invalid web version" in result.stderr
            assert (ROOT / "builds/itch-web/build.json").read_bytes() == before
    finally:
        check(None)
    print("[itch-version] PASS tag, default, archive, cache keys, invalid input")
