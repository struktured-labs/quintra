#!/usr/bin/env python3
"""
Boot & No-Crash Verification for Penta Dragon DX.

Tests:
1. Boot test: game starts, FFC1=1, D880 transitions properly
2. No-crash test: run 60s of gameplay without hanging

Usage:
    uv run python scripts/verify_boot.py [rom_path]
    uv run python scripts/verify_boot.py --mode nocrash [rom_path]

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
LUA_SCRIPT = PROJECT_ROOT / "scripts" / "verify_boot.lua"
TMP_DIR = PROJECT_ROOT / "tmp" / "verify"


def run_boot_test(rom_path: str, mode: str = "boot") -> dict:
    """Run boot/nocrash verification on a ROM."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    report_path = TMP_DIR / f"verify_boot_{mode}.json"

    # Clean up previous artifacts
    for marker in ["DONE_VERIFY_BOOT"]:
        p = PROJECT_ROOT / marker
        if p.exists():
            p.unlink()

    env = os.environ.copy()
    env["VERIFY_OUTPUT"] = str(report_path)
    env["VERIFY_MODE"] = mode
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["SDL_AUDIODRIVER"] = "dummy"
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)

    if mode == "boot":
        max_frames = 900  # Need ~816 frames for D880 to reach dungeon state
        timeout_sec = 30
    else:  # nocrash
        max_frames = 3600  # 60 seconds
        timeout_sec = 120

    env["VERIFY_MAX_FRAMES"] = str(max_frames)
    env["VERIFY_NOCRASH_FRAMES"] = str(max_frames)

    cmd = [
        "xvfb-run", "-a", MGBA, str(rom_path),
        "--script", str(LUA_SCRIPT), "-l", "0"
    ]

    try:
        subprocess.run(cmd, env=env, timeout=timeout_sec,
                       capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    except subprocess.TimeoutExpired:
        # Timeout is EXPECTED: emu:quit() doesn't exit mgba-qt.
        # The Lua script writes the report before calling quit,
        # so check if the report file was generated.
        pass
    except FileNotFoundError:
        return {"passed": False, "error": f"mgba-qt not found at {MGBA}"}

    if not report_path.exists():
        return {"passed": False, "error": "No report generated - emulator may have crashed"}

    with open(report_path) as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Boot/No-Crash Verification")
    parser.add_argument("rom", nargs="?", default=str(DEFAULT_DX_ROM),
                        help="ROM path (default: DX v288)")
    parser.add_argument("--mode", choices=["boot", "nocrash"], default="boot",
                        help="Test mode: boot (quick) or nocrash (60s)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    if not Path(args.rom).exists():
        # Try FIXED fallback
        fixed = PROJECT_ROOT / "rom" / "working" / "penta_dragon_dx_FIXED.gb"
        if fixed.exists():
            args.rom = str(fixed)
        else:
            print(f"ERROR: ROM not found: {args.rom}")
            sys.exit(2)

    result = run_boot_test(args.rom, args.mode)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        mode_label = "BOOT" if args.mode == "boot" else "NO-CRASH"
        passed = result.get("passed", False)
        print(f"[{mode_label}] {'PASS' if passed else 'FAIL'}")
        if result.get("ffc1_frame", -1) > 0:
            print(f"  FFC1=1 at frame {result['ffc1_frame']}")
        if result.get("d880_reached_dungeon"):
            print(f"  D880=2 (dungeon) at frame {result.get('d880_dungeon_frame', '?')}")
        if result.get("d880_change_count", 0) > 0:
            print(f"  D880 state changes: {result['d880_change_count']}")
        if result.get("lcdc_off_frames", 0) > 0:
            print(f"  LCDC disabled frames: {result['lcdc_off_frames']}")
        if result.get("error"):
            print(f"  Error: {result['error']}")

    sys.exit(0 if result.get("passed", False) else 1)


if __name__ == "__main__":
    main()
