#!/usr/bin/env python3
"""
Dual-ROM Frame Comparison for Penta Dragon DX.

Runs original and DX ROMs with IDENTICAL input for N frames,
dumps key memory addresses each frame, and compares them.

Reports first divergence point and total divergence count.

Usage:
    uv run python scripts/dual_rom_compare.py
    uv run python scripts/dual_rom_compare.py --frames 1200
    uv run python scripts/dual_rom_compare.py --json

Exit codes:
    0 = Synchronized (no critical divergences)
    1 = Divergences detected
    2 = ERROR
"""
import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MGBA = os.getenv("MGBA_PATH", "/home/struktured/bin/mgba-qt")
ORIG_ROM = PROJECT_ROOT / "rom" / "Penta Dragon (J).gb"
DEFAULT_DX_ROM = PROJECT_ROOT / "rom" / "working" / "penta_dragon_dx_v288.gb"
LUA_SCRIPT = PROJECT_ROOT / "scripts" / "dual_rom_compare.lua"
TMP_DIR = PROJECT_ROOT / "tmp" / "verify" / "dual"

# Fields where divergence is EXPECTED (DX modifies these by design)
EXPECTED_DIVERGENCE_FIELDS = {"DCDD"}  # We write infinite HP

# Fields where divergence is CRITICAL
CRITICAL_FIELDS = {"D880", "FFC1", "FFBD", "FFCF"}


@dataclass
class Divergence:
    frame: int
    field: str
    orig_value: int
    dx_value: int


def run_rom(rom_path: str, label: str, max_frames: int, dump_interval: int) -> str:
    """Run a ROM and dump state CSV. Returns path to CSV."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    # Clean markers
    marker = PROJECT_ROOT / f"DONE_DUAL_{label}"
    if marker.exists():
        marker.unlink()

    env = os.environ.copy()
    env["VERIFY_DUMP_DIR"] = str(TMP_DIR)
    env["VERIFY_MAX_FRAMES"] = str(max_frames)
    env["VERIFY_ROM_LABEL"] = label
    env["VERIFY_DUMP_INTERVAL"] = str(dump_interval)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["SDL_AUDIODRIVER"] = "dummy"
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)

    cmd = [
        "xvfb-run", "-a", MGBA, str(rom_path),
        "--script", str(LUA_SCRIPT), "-l", "0"
    ]

    timeout_sec = max_frames // 30 + 30

    try:
        subprocess.run(cmd, env=env, timeout=timeout_sec,
                       capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    except subprocess.TimeoutExpired:
        pass
    except FileNotFoundError:
        print(f"ERROR: mgba-qt not found at {MGBA}")
        sys.exit(2)

    csv_path = TMP_DIR / f"state_{label}.csv"
    return str(csv_path)


def load_states(csv_path: str) -> dict:
    """Load state CSV into {frame: {field: value}} dict."""
    states = {}
    if not os.path.exists(csv_path):
        return states

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            frame = int(row["frame"])
            states[frame] = {k: int(v) for k, v in row.items() if k != "frame"}

    return states


def compare_states(orig_states: dict, dx_states: dict) -> dict:
    """Compare two state sequences and find divergences."""
    divergences = []
    first_divergence = None

    # Only compare frames present in both
    common_frames = sorted(set(orig_states.keys()) & set(dx_states.keys()))

    # Skip first 400 frames (title menu - timing may differ slightly)
    gameplay_frames = [f for f in common_frames if f >= 400]

    for frame in gameplay_frames:
        orig = orig_states[frame]
        dx = dx_states[frame]

        for field in orig:
            if field == "keys":
                continue  # Same inputs
            if field in EXPECTED_DIVERGENCE_FIELDS:
                continue

            orig_val = orig.get(field, -1)
            dx_val = dx.get(field, -1)

            if orig_val != dx_val:
                div = Divergence(frame, field, orig_val, dx_val)
                divergences.append(div)
                if first_divergence is None:
                    first_divergence = div

    # Count by field
    field_counts = {}
    for d in divergences:
        field_counts[d.field] = field_counts.get(d.field, 0) + 1

    # Critical divergences
    critical = [d for d in divergences if d.field in CRITICAL_FIELDS]

    return {
        "total_common_frames": len(common_frames),
        "gameplay_frames": len(gameplay_frames),
        "total_divergences": len(divergences),
        "critical_divergences": len(critical),
        "first_divergence": {
            "frame": first_divergence.frame,
            "field": first_divergence.field,
            "orig": first_divergence.orig_value,
            "dx": first_divergence.dx_value,
        } if first_divergence else None,
        "field_counts": field_counts,
        "first_10_critical": [
            {"frame": d.frame, "field": d.field, "orig": d.orig_value, "dx": d.dx_value}
            for d in critical[:10]
        ],
        "passed": len(critical) == 0,
    }


def main():
    parser = argparse.ArgumentParser(description="Dual-ROM Frame Comparison")
    parser.add_argument("--dx-rom", default=str(DEFAULT_DX_ROM), help="DX ROM path")
    parser.add_argument("--orig-rom", default=str(ORIG_ROM), help="Original ROM path")
    parser.add_argument("--frames", type=int, default=600, help="Max frames (default 600)")
    parser.add_argument("--interval", type=int, default=5,
                        help="Dump interval in frames (default 5)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    dx_rom = Path(args.dx_rom)
    if not dx_rom.exists():
        fixed = PROJECT_ROOT / "rom" / "working" / "penta_dragon_dx_FIXED.gb"
        if fixed.exists():
            dx_rom = fixed
        else:
            print(f"ERROR: DX ROM not found: {args.dx_rom}")
            sys.exit(2)

    if not Path(args.orig_rom).exists():
        print(f"ERROR: Original ROM not found: {args.orig_rom}")
        sys.exit(2)

    print(f"[DUAL] Running original ROM ({args.frames} frames)...")
    orig_csv = run_rom(args.orig_rom, "original", args.frames, args.interval)

    print(f"[DUAL] Running DX ROM ({args.frames} frames)...")
    dx_csv = run_rom(str(dx_rom), "dx", args.frames, args.interval)

    print("[DUAL] Comparing states...")
    orig_states = load_states(orig_csv)
    dx_states = load_states(dx_csv)

    if not orig_states:
        print("ERROR: No original ROM states captured")
        sys.exit(2)
    if not dx_states:
        print("ERROR: No DX ROM states captured")
        sys.exit(2)

    result = compare_states(orig_states, dx_states)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        passed = result.get("passed", False)
        print(f"\n[DUAL] {'PASS' if passed else 'FAIL'}")
        print(f"  Frames compared: {result['gameplay_frames']}")
        print(f"  Total divergences: {result['total_divergences']}")
        print(f"  Critical divergences: {result['critical_divergences']}")

        if result.get("first_divergence"):
            fd = result["first_divergence"]
            print(f"  First divergence: frame {fd['frame']}, "
                  f"{fd['field']} orig={fd['orig']} dx={fd['dx']}")

        if result.get("field_counts"):
            print("  By field:")
            for field, count in sorted(result["field_counts"].items(),
                                        key=lambda x: -x[1]):
                marker = " [CRITICAL]" if field in CRITICAL_FIELDS else ""
                print(f"    {field}: {count}{marker}")

    # Save full report
    report_path = TMP_DIR / "dual_compare_report.json"
    with open(report_path, "w") as f:
        json.dump(result, f, indent=2)

    sys.exit(0 if result.get("passed", False) else 1)


if __name__ == "__main__":
    main()
