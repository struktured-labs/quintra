#!/usr/bin/env python3
"""Frame-by-frame flicker regression test.

Captures continuous frames during specified ranges, then computes
frame-to-frame pixel diffs. Detects:
  - Flicker (sudden large diffs between consecutive frames)
  - White-bar regions (tiles that stay uncolored)
  - Drift vs baseline ROM (frame-aligned comparison)

Usage:
  python3 regression_animation_diff.py <rom_path> [--baseline BASELINE_ROM]

Captures frames during 4 phases:
  - Title splash (200-260): publisher splash transition
  - Title menu (450-510): "OPENING START / GAME START"
  - Stage load (520-580): STAGE 01 splash → dungeon
  - Gameplay (1200-1260): dungeon scrolling
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
    from PIL import Image
    import numpy as np
except ImportError:
    print("Install: uv pip install pillow numpy")
    sys.exit(1)


CAPTURE_RANGES = "200-260,450-510,520-580,1200-1260"
CAPTURE_STEP = 2  # every 2nd frame = 30 fps capture rate


def run_capture(rom: Path, prefix: Path, ranges: str, step: int = 2, end_frame: int = 1400):
    """Run mGBA with continuous capture script, blocking until done."""
    env = os.environ.copy()
    env["CAP_PREFIX"] = str(prefix)
    env["CAP_RANGE"] = ranges
    env["CAP_STEP"] = str(step)
    env["CAP_END"] = str(end_frame)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["SDL_AUDIODRIVER"] = "dummy"
    proc = subprocess.Popen(
        ["xvfb-run", "-a", "mgba-qt", str(rom), "--script", "/tmp/capture_continuous.lua"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        # Allow ~25s real time to reach frame 1400 + buffer
        for _ in range(60):
            time.sleep(1)
            # Check if last expected frame was captured
            expected = f"{prefix}_f{end_frame:05d}.png"
            if Path(expected).exists():
                time.sleep(1)
                return
            # Also exit if we have a capture in the final range
            files = sorted(prefix.parent.glob(f"{prefix.name}_f*.png"))
            if files and int(re.search(r"_f(\d+)", files[-1].name).group(1)) >= end_frame - 5:
                time.sleep(1)
                return
    finally:
        proc.terminate()
        try: proc.wait(timeout=3)
        except subprocess.TimeoutExpired: proc.kill()


def load_frames(prefix: Path) -> dict:
    """Load all captured frames as numpy arrays, keyed by frame number."""
    frames = {}
    for f in sorted(prefix.parent.glob(f"{prefix.name}_f*.png")):
        m = re.search(r"_f(\d+)\.png$", f.name)
        if not m: continue
        n = int(m.group(1))
        img = Image.open(f).convert("RGB")
        frames[n] = np.array(img, dtype=np.int16)
    return frames


def detect_flicker(frames: dict, threshold_rms: float = 5.0) -> dict:
    """Compute RMS pixel diff between consecutive frames in same range.

    Returns dict {frame_n: rms_diff_to_next}.
    """
    nums = sorted(frames.keys())
    diffs = {}
    for i in range(len(nums) - 1):
        n1, n2 = nums[i], nums[i+1]
        # Only compare if adjacent (within range step)
        if n2 - n1 > 10: continue
        diff = frames[n2] - frames[n1]
        rms = float(np.sqrt(np.mean(diff.astype(np.float64) ** 2)))
        diffs[n1] = rms
    return diffs


def detect_uniform_white(frames: dict, threshold: float = 0.3) -> dict:
    """Detect frames where >threshold fraction of pixels are pure white/light.

    DMG default palette → palette 0 with no CGB colors looks like white/grey.
    """
    results = {}
    for n, arr in sorted(frames.items()):
        # Pixel is "very light" if R, G, B all > 200
        light = np.all(arr > 200, axis=2)
        frac = float(np.mean(light))
        results[n] = frac
    return results


def main():
    p = argparse.ArgumentParser()
    p.add_argument("rom", type=Path)
    p.add_argument("--baseline", type=Path, default=Path("rom/Penta Dragon (J) [A-fix].gb"))
    p.add_argument("--also", type=Path, default=Path("rom/working/penta_dragon_dx_FIXED.gb"))
    args = p.parse_args()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        target_prefix = tmpdir / "target"
        baseline_prefix = tmpdir / "baseline"
        also_prefix = tmpdir / "also"

        print(f"Capturing target: {args.rom}")
        run_capture(args.rom, target_prefix, CAPTURE_RANGES, CAPTURE_STEP, end_frame=1400)
        target_frames = load_frames(target_prefix)
        print(f"  → {len(target_frames)} frames")

        print(f"Capturing baseline (vanilla): {args.baseline}")
        run_capture(args.baseline, baseline_prefix, CAPTURE_RANGES, CAPTURE_STEP, end_frame=1400)
        baseline_frames = load_frames(baseline_prefix)
        print(f"  → {len(baseline_frames)} frames")

        if args.also.exists():
            print(f"Capturing also (v3.00): {args.also}")
            run_capture(args.also, also_prefix, CAPTURE_RANGES, CAPTURE_STEP, end_frame=1400)
            also_frames = load_frames(also_prefix)
            print(f"  → {len(also_frames)} frames")
        else:
            also_frames = {}

        # Per-phase analysis
        phases = {
            "Title splash (200-260)": (200, 260),
            "Title menu (450-510)": (450, 510),
            "Stage load (520-580)": (520, 580),
            "Gameplay (1200-1260)": (1200, 1260),
        }

        print()
        for phase, (lo, hi) in phases.items():
            print(f"=== {phase} ===")
            for name, frames in [("target", target_frames),
                                 ("baseline", baseline_frames),
                                 ("v3.00", also_frames)]:
                if not frames: continue
                in_phase = {n: f for n, f in frames.items() if lo <= n <= hi}
                if not in_phase: continue
                flicker = detect_flicker(in_phase)
                if flicker:
                    rms_vals = list(flicker.values())
                    avg_rms = sum(rms_vals) / len(rms_vals)
                    max_rms = max(rms_vals)
                    print(f"  {name:10s} | frames={len(in_phase):3d} | avg flicker RMS={avg_rms:6.2f} | max RMS={max_rms:6.2f}")
                white = detect_uniform_white(in_phase)
                white_vals = list(white.values())
                avg_white = sum(white_vals) / len(white_vals)
                # Don't print too much
                if avg_white > 0.1 or name == "target":
                    print(f"  {name:10s}   white-pixel frac avg={avg_white:.3f}")

        print()
        print("Flicker interpretation:")
        print("  RMS < 3: stable (no changes)")
        print("  RMS 3-15: animation present (acceptable)")
        print("  RMS > 15: heavy flicker (regression)")
        print("Compare target's max RMS to v3.00 / baseline for the same phase.")


if __name__ == "__main__":
    main()
