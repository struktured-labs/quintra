#!/usr/bin/env python3
"""
Color Regression Verification for Penta Dragon DX.

Runs the DX ROM, enters gameplay, and checks VRAM palette attributes
against expected values from the bg_tile_table and OBJ tile mapping.

PASS criteria: >90% BG tiles correct, >90% OBJ sprites correct.

Usage:
    uv run python scripts/verify_colors.py [rom_path]
    uv run python scripts/verify_colors.py --json

Exit codes:
    0 = PASS
    1 = FAIL
    2 = ERROR
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MGBA = os.getenv("MGBA_PATH", "/home/struktured/bin/mgba-qt")
DEFAULT_DX_ROM = PROJECT_ROOT / "rom" / "working" / "penta_dragon_dx_v288.gb"
LUA_SCRIPT = PROJECT_ROOT / "scripts" / "verify_colors.lua"
TMP_DIR = PROJECT_ROOT / "tmp" / "verify"


def run_color_test(rom_path: str) -> dict:
    """Run color verification on a ROM."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    report_path = TMP_DIR / "verify_colors_report.json"

    # Clean markers
    marker = PROJECT_ROOT / "DONE_VERIFY_COLORS"
    if marker.exists():
        marker.unlink()

    env = os.environ.copy()
    env["VERIFY_OUTPUT"] = str(report_path)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["SDL_AUDIODRIVER"] = "dummy"
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)

    cmd = [
        "xvfb-run", "-a", MGBA, str(rom_path),
        "--script", str(LUA_SCRIPT), "-l", "0"
    ]

    try:
        subprocess.run(cmd, env=env, timeout=45,
                       capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    except subprocess.TimeoutExpired:
        # Timeout is expected: emu:quit() doesn't exit mgba-qt.
        # Check if report was generated below.
        pass
    except FileNotFoundError:
        return {"passed": False, "error": f"mgba-qt not found at {MGBA}"}

    if not report_path.exists():
        return {"passed": False, "error": "No report generated"}

    with open(report_path) as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Color Regression Verification")
    parser.add_argument("rom", nargs="?", default=str(DEFAULT_DX_ROM),
                        help="ROM path")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    rom = Path(args.rom)
    if not rom.exists():
        fixed = PROJECT_ROOT / "rom" / "working" / "penta_dragon_dx_FIXED.gb"
        if fixed.exists():
            rom = fixed
        else:
            print(f"ERROR: ROM not found: {args.rom}")
            sys.exit(2)

    result = run_color_test(str(rom))

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        passed = result.get("passed", False)
        print(f"[COLORS] {'PASS' if passed else 'FAIL'}")

        bg_acc = result.get("bg_accuracy", 0)
        obj_acc = result.get("obj_accuracy", 0)
        print(f"  BG tiles:  {result.get('bg_correct', 0)}/{result.get('bg_total', 0)} "
              f"({bg_acc:.1f}%) {'PASS' if result.get('bg_pass') else 'FAIL'}")
        print(f"  OBJ sprites: {result.get('obj_correct', 0)}/{result.get('obj_total', 0)} "
              f"({obj_acc:.1f}%) {'PASS' if result.get('obj_pass') else 'FAIL'}")

        if result.get("bg_errors"):
            print("  BG errors (first 10):")
            for err in result["bg_errors"][:10]:
                if isinstance(err, dict):
                    print(f"    tile={err.get('tile')} expected={err.get('expected')} "
                          f"actual={err.get('actual')} at ({err.get('x')},{err.get('y')})")

        if result.get("obj_errors"):
            print("  OBJ errors (first 10):")
            for err in result["obj_errors"][:10]:
                if isinstance(err, dict):
                    print(f"    slot={err.get('slot')} tile={err.get('tile')} "
                          f"expected={err.get('expected')} actual={err.get('actual')}")

        if result.get("error"):
            print(f"  Error: {result['error']}")

    sys.exit(0 if result.get("passed", False) else 1)


if __name__ == "__main__":
    main()
