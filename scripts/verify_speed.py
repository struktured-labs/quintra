#!/usr/bin/env python3
"""
Speed Verification for Penta Dragon DX.

Runs both original and DX ROMs with identical input (walk RIGHT for 10s),
compares game state advancement rates.

PASS criteria: DX scroll/advancement within +/-5% of original.

Usage:
    uv run python scripts/verify_speed.py
    uv run python scripts/verify_speed.py --dx-rom rom/working/custom.gb

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
ORIG_ROM = PROJECT_ROOT / "rom" / "Penta Dragon (J).gb"
DEFAULT_DX_ROM = PROJECT_ROOT / "rom" / "working" / "penta_dragon_dx_v288.gb"
LUA_SCRIPT = PROJECT_ROOT / "scripts" / "verify_speed.lua"
TMP_DIR = PROJECT_ROOT / "tmp" / "verify"

TOLERANCE = 0.05  # 5% deviation allowed


def run_speed_test(rom_path: str, label: str) -> dict:
    """Run speed test on a single ROM."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    report_path = TMP_DIR / f"verify_speed_{label}.json"

    # Clean markers
    marker = PROJECT_ROOT / f"DONE_VERIFY_SPEED_{label}"
    if marker.exists():
        marker.unlink()

    env = os.environ.copy()
    env["VERIFY_OUTPUT"] = str(report_path)
    env["VERIFY_ROM_LABEL"] = label
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["SDL_AUDIODRIVER"] = "dummy"
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)

    cmd = [
        "xvfb-run", "-a", MGBA, str(rom_path),
        "--script", str(LUA_SCRIPT), "-l", "0"
    ]

    try:
        subprocess.run(cmd, env=env, timeout=60,
                       capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    except subprocess.TimeoutExpired:
        # Timeout is expected: emu:quit() doesn't exit mgba-qt.
        # Check if report was generated below.
        pass
    except FileNotFoundError:
        return {"error": f"mgba-qt not found at {MGBA}"}

    if not report_path.exists():
        return {"error": f"No report generated for {label}"}

    with open(report_path) as f:
        return json.load(f)


def compare_results(orig: dict, dx: dict) -> dict:
    """Compare original and DX speed metrics."""
    if "error" in orig or "error" in dx:
        return {
            "passed": False,
            "error": orig.get("error", "") or dx.get("error", ""),
            "original": orig,
            "dx": dx,
        }

    metrics = {}
    all_pass = True

    # oam_changes excluded from pass/fail — OBJ colorizer is intentionally throttled
    for key in ["scroll_ticks", "dc81_changes"]:
        orig_val = orig.get(key, 0)
        dx_val = dx.get(key, 0)

        if orig_val == 0:
            # Can't compare if original has no movement
            ratio = 1.0
            within_tolerance = True
        else:
            ratio = dx_val / orig_val
            within_tolerance = abs(1.0 - ratio) <= TOLERANCE

        metrics[key] = {
            "original": orig_val,
            "dx": dx_val,
            "ratio": round(ratio, 3),
            "within_tolerance": within_tolerance,
        }
        if not within_tolerance:
            all_pass = False

    # Add oam_changes as informational only (not in pass/fail)
    orig_oam = orig.get("oam_changes", 0)
    dx_oam = dx.get("oam_changes", 0)
    metrics["oam_changes"] = {
        "original": orig_oam,
        "dx": dx_oam,
        "ratio": round(dx_oam / orig_oam, 3) if orig_oam > 0 else 1.0,
        "within_tolerance": True,  # Always passes (informational)
        "info_only": True,
    }

    return {
        "passed": all_pass,
        "tolerance": TOLERANCE,
        "metrics": metrics,
        "original": orig,
        "dx": dx,
    }


def main():
    parser = argparse.ArgumentParser(description="Speed Verification")
    parser.add_argument("--dx-rom", default=str(DEFAULT_DX_ROM),
                        help="DX ROM path")
    parser.add_argument("--orig-rom", default=str(ORIG_ROM),
                        help="Original ROM path")
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

    print("[SPEED] Running original ROM...")
    orig_result = run_speed_test(args.orig_rom, "original")

    print("[SPEED] Running DX ROM...")
    dx_result = run_speed_test(str(dx_rom), "dx")

    comparison = compare_results(orig_result, dx_result)

    if args.json:
        print(json.dumps(comparison, indent=2))
    else:
        passed = comparison.get("passed", False)
        print(f"\n[SPEED] {'PASS' if passed else 'FAIL'}")

        if "metrics" in comparison:
            for key, m in comparison["metrics"].items():
                status = "OK" if m["within_tolerance"] else "DEVIATION"
                print(f"  {key}: orig={m['original']} dx={m['dx']} "
                      f"ratio={m['ratio']:.3f} [{status}]")

        if comparison.get("error"):
            print(f"  Error: {comparison['error']}")

    # Save full report
    report_path = TMP_DIR / "verify_speed_report.json"
    with open(report_path, "w") as f:
        json.dump(comparison, f, indent=2)

    sys.exit(0 if comparison.get("passed", False) else 1)


if __name__ == "__main__":
    main()
