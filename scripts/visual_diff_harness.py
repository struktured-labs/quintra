#!/usr/bin/env python3
"""Visual regression diff harness.

Captures continuous frames from target ROM and baseline ROMs at identical
emulated timestamps, then composes side-by-side comparison images for each
captured frame, with a per-pixel diff overlay highlighting changes.

Output: tmp/visual_diff/{phase}_{frame}.png with 3-panel layout:
  [vanilla baseline] [target ROM] [diff highlight]

Usage:
  python3 visual_diff_harness.py rom/working/penta_dragon_dx_v301.gb
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
except ImportError:
    print("Install: uv pip install pillow numpy")
    sys.exit(1)


# Capture ranges chosen to cover scenarios user reports issues:
# - Title splash + menu (200-260, 430-510)
# - Dungeon scrolling (1000-1080)
# - Stage load transition (510-540)
PHASES = {
    "title_splash": (200, 260, 4),     # every 4 frames
    "title_menu":   (430, 510, 4),
    "stage_load":   (510, 540, 4),
    "scroll":       (1000, 1080, 4),
}


CAPTURE_LUA = '''
local PREFIX = os.getenv("CAP_PREFIX")
local RANGES = os.getenv("CAP_RANGES")
local KEY_A=0x01; local KEY_START=0x08
local KEY_RIGHT=0x10; local KEY_LEFT=0x20; local KEY_UP=0x40; local KEY_DOWN=0x80
local TITLE = {{180,185,KEY_DOWN},{193,198,KEY_A},{241,246,KEY_A},
               {291,296,KEY_A},{341,346,KEY_START},{391,396,KEY_A}}
local ranges = {}
for r in RANGES:gmatch("([^,]+)") do
    local s, e, st = r:match("(%d+)%-(%d+):(%d+)")
    if s and e and st then table.insert(ranges, {tonumber(s), tonumber(e), tonumber(st)}) end
end
local f = 0
local end_frame = 1200
local done = false
callbacks:add("frame", function()
    if done then return end
    f = f + 1
    if f <= 500 then
        local k = 0
        for _, e in ipairs(TITLE) do
            if f >= e[1] and f <= e[2] then k = e[3]; break end
        end
        emu:setKeys(k)
    else
        local keys = KEY_A
        if (f % 30) < 5 then keys = keys + KEY_UP
        elseif (f % 30) < 10 then keys = keys + KEY_DOWN
        elseif (f % 30) < 15 then keys = keys + KEY_LEFT
        elseif (f % 30) < 20 then keys = keys + KEY_RIGHT
        end
        emu:setKeys(keys)
    end
    for _, r in ipairs(ranges) do
        if f >= r[1] and f <= r[2] and (f - r[1]) % r[3] == 0 then
            emu:screenshot(string.format("%s_f%05d.png", PREFIX, f))
            break
        end
    end
    if f >= end_frame then done = true end
end)
'''


def run_capture(rom: Path, prefix: Path, ranges_str: str):
    """Run mGBA, capturing screenshots per ranges_str (e.g. "200-260:4,1000-1080:4")."""
    lua_path = Path("/tmp/visual_diff_capture.lua")
    lua_path.write_text(CAPTURE_LUA)
    env = {
        "HOME": os.environ.get("HOME", "/tmp"),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "QT_QPA_PLATFORM": "offscreen",
        "SDL_AUDIODRIVER": "dummy",
        "CAP_PREFIX": str(prefix),
        "CAP_RANGES": ranges_str,
    }
    # Clean up any stale X locks
    subprocess.run(["bash", "-c", "rm -f /tmp/.X*-lock"], capture_output=True)
    proc = subprocess.Popen(
        ["xvfb-run", "-a", "mgba-qt", str(rom), "--script", str(lua_path)],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    # Wait until last expected file or timeout (~30s for frame 1200)
    try:
        for _ in range(45):
            time.sleep(1)
            files = sorted(prefix.parent.glob(f"{prefix.name}_f*.png"))
            if files and int(re.search(r"_f(\d+)", files[-1].name).group(1)) >= 1180:
                time.sleep(2)
                return
    finally:
        proc.terminate()
        try: proc.wait(timeout=3)
        except subprocess.TimeoutExpired: proc.kill()


def make_diff_image(baseline_path: Path, target_path: Path, output_path: Path,
                    label_baseline: str = "vanilla", label_target: str = "target"):
    """Produce 3-panel side-by-side: baseline | target | diff highlight."""
    b = Image.open(baseline_path).convert("RGB")
    t = Image.open(target_path).convert("RGB")
    # Ensure same size
    w, h = b.size
    if t.size != (w, h):
        t = t.resize((w, h))
    bn = np.array(b, dtype=np.int16)
    tn = np.array(t, dtype=np.int16)
    diff_abs = np.abs(bn - tn).sum(axis=2)  # per-pixel abs diff sum across RGB
    # Highlight diff: white where same, red where different
    diff_vis = np.zeros((h, w, 3), dtype=np.uint8)
    diff_vis[..., 0] = np.where(diff_abs > 30, 255, 0)
    diff_vis[..., 1] = np.where(diff_abs > 30, 100, 0)
    # Overlay target on diff for context
    diff_img = Image.fromarray(diff_vis)
    diff_img = Image.blend(t, diff_img, alpha=0.4)
    # 3-panel: [baseline | target | diff] at 3x scale
    scale = 3
    pw, ph = w * scale, h * scale
    canvas = Image.new("RGB", (pw * 3 + 20, ph + 30), color=(20, 20, 20))
    b3 = b.resize((pw, ph), Image.NEAREST)
    t3 = t.resize((pw, ph), Image.NEAREST)
    d3 = diff_img.resize((pw, ph), Image.NEAREST)
    canvas.paste(b3, (0, 30))
    canvas.paste(t3, (pw + 10, 30))
    canvas.paste(d3, (2 * (pw + 10), 30))
    # Labels
    try:
        from PIL import ImageDraw
        draw = ImageDraw.Draw(canvas)
        draw.text((10, 5), label_baseline, fill=(200, 200, 200))
        draw.text((pw + 20, 5), label_target, fill=(200, 200, 200))
        draw.text((2 * (pw + 10) + 10, 5), "diff (red=changed)", fill=(255, 200, 200))
    except ImportError:
        pass
    canvas.save(output_path)
    return float(diff_abs.mean())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("target", type=Path, help="ROM to test")
    p.add_argument("--baseline", type=Path, default=Path("rom/working/penta_dragon_dx_FIXED.gb"),
                   help="Baseline ROM (default: v3.00 FIXED)")
    p.add_argument("--out", type=Path, default=Path("tmp/visual_diff"))
    args = p.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    # Combine all phases into one range string
    ranges_str = ",".join(f"{lo}-{hi}:{step}" for lo, hi, step in PHASES.values())

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        target_prefix = tmpdir / "target"
        baseline_prefix = tmpdir / "baseline"

        print(f"Capturing target: {args.target.name}")
        run_capture(args.target, target_prefix, ranges_str)
        n_target = len(list(target_prefix.parent.glob(f"{target_prefix.name}_f*.png")))
        print(f"  → {n_target} frames")

        print(f"Capturing baseline: {args.baseline.name}")
        run_capture(args.baseline, baseline_prefix, ranges_str)
        n_baseline = len(list(baseline_prefix.parent.glob(f"{baseline_prefix.name}_f*.png")))
        print(f"  → {n_baseline} frames")

        # Build diff images per phase
        print("\nGenerating diffs:")
        for phase, (lo, hi, step) in PHASES.items():
            phase_dir = args.out / phase
            phase_dir.mkdir(exist_ok=True)
            diffs = []
            for f in range(lo, hi + 1, step):
                t_path = target_prefix.parent / f"{target_prefix.name}_f{f:05d}.png"
                b_path = baseline_prefix.parent / f"{baseline_prefix.name}_f{f:05d}.png"
                if not (t_path.exists() and b_path.exists()):
                    continue
                out = phase_dir / f"f{f:05d}.png"
                avg_diff = make_diff_image(b_path, t_path, out,
                                           label_baseline=f"v3.00 baseline f{f}",
                                           label_target=f"{args.target.stem} f{f}")
                diffs.append(avg_diff)
            if diffs:
                print(f"  {phase:14s}: {len(diffs)} frames, avg pixel diff={sum(diffs)/len(diffs):.1f}, max={max(diffs):.1f}")
                print(f"                → {phase_dir.relative_to(args.out.parent)}/")

    print(f"\nDone. View images in {args.out}/")


if __name__ == "__main__":
    main()
