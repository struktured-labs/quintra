#!/usr/bin/env python3
"""
Automated Colorization Verification Suite

Runs comprehensive tests to detect:
1. OAM palette flickering (sprite color instability)
2. BG attribute flickering (background color instability)
3. Performance issues (game slowdown from VBlank overhead)

Usage:
    uv run python scripts/verify_colorization.py [rom_path] [--savestate path]

Exit codes:
    0 = All tests passed
    1 = One or more tests failed
"""

import json
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class TestResult:
    """Result of a single verification test."""
    name: str
    passed: bool
    details: dict
    error: Optional[str] = None


@dataclass
class VerificationReport:
    """Complete verification report."""
    passed: bool
    results: list[TestResult]
    rom_path: str
    savestate_path: Optional[str]


# Paths
SCRIPT_DIR = Path(__file__).parent
LUA_DIR = SCRIPT_DIR / "lua"
PROJECT_ROOT = SCRIPT_DIR.parent


def find_mgba():
    """Find mgba-qt executable."""
    candidates = [
        "/usr/local/bin/mgba-qt",
        "/usr/bin/mgba-qt",
        "mgba-qt",
    ]
    for path in candidates:
        try:
            result = subprocess.run(
                [path, "--version"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                return path
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    return None


def run_lua_test(
    rom_path: str,
    lua_script: str,
    output_file: str,
    savestate_path: Optional[str] = None,
    timeout_seconds: int = 60
) -> Optional[dict]:
    """
    Run a Lua test script via mgba-qt headless.

    Returns parsed JSON output or None on failure.
    """
    mgba = find_mgba()
    if not mgba:
        print("ERROR: mgba-qt not found", file=sys.stderr)
        return None

    # Create temp directory for test outputs
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Copy Lua script to temp dir (mGBA writes output to CWD)
        lua_path = LUA_DIR / lua_script
        if not lua_path.exists():
            print(f"ERROR: Lua script not found: {lua_path}", file=sys.stderr)
            return None

        test_lua = tmpdir / lua_script
        test_lua.write_text(lua_path.read_text())

        # Build command
        cmd = [
            "xvfb-run", "-a",
            mgba,
            str(rom_path),
            "--script", str(test_lua),
            "-l", "0",  # Log level
        ]

        if savestate_path:
            cmd.extend(["-t", str(savestate_path)])

        # Set environment for headless operation
        import os
        env = os.environ.copy()
        env["SDL_AUDIODRIVER"] = "dummy"
        env.pop("DISPLAY", None)  # Force headless

        try:
            # Run mgba-qt
            process = subprocess.Popen(
                cmd,
                cwd=str(tmpdir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Wait for completion with timeout
            start_time = time.time()
            done_file = tmpdir / "DONE"

            while time.time() - start_time < timeout_seconds:
                if done_file.exists():
                    break
                time.sleep(0.5)

                # Check if process died
                if process.poll() is not None:
                    break

            # Kill if still running
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()

            # Read output file
            output_path = tmpdir / output_file
            if output_path.exists():
                try:
                    return json.loads(output_path.read_text())
                except json.JSONDecodeError as e:
                    print(f"ERROR: Failed to parse {output_file}: {e}", file=sys.stderr)
                    print(f"Content: {output_path.read_text()[:500]}", file=sys.stderr)
                    return None
            else:
                print(f"ERROR: Output file not created: {output_file}", file=sys.stderr)
                # Print any stderr from mgba
                stderr = process.stderr.read().decode() if process.stderr else ""
                if stderr:
                    print(f"mGBA stderr: {stderr[:500]}", file=sys.stderr)
                return None

        except Exception as e:
            print(f"ERROR: Failed to run test: {e}", file=sys.stderr)
            return None


def run_oam_stability_test(
    rom_path: str,
    savestate_path: Optional[str] = None
) -> TestResult:
    """Run OAM stability test to detect sprite palette flickering."""
    print("Running OAM stability test...")

    result = run_lua_test(
        rom_path,
        "oam_stability_test.lua",
        "oam_stability_report.json",
        savestate_path,
        timeout_seconds=30
    )

    if result is None:
        return TestResult(
            name="oam_stability",
            passed=False,
            details={},
            error="Test execution failed"
        )

    # Thresholds
    FLICKER_THRESHOLD = 0  # Zero tolerance for palette flickering

    passed = result.get("flicker_count", 999) <= FLICKER_THRESHOLD

    return TestResult(
        name="oam_stability",
        passed=passed,
        details=result,
        error=None if passed else f"Detected {result.get('flicker_count', '?')} palette flickers"
    )


def run_bg_stability_test(
    rom_path: str,
    savestate_path: Optional[str] = None
) -> TestResult:
    """Run BG stability test to detect background attribute flickering."""
    print("Running BG stability test...")

    result = run_lua_test(
        rom_path,
        "bg_stability_test.lua",
        "bg_stability_report.json",
        savestate_path,
        timeout_seconds=20
    )

    if result is None:
        return TestResult(
            name="bg_stability",
            passed=False,
            details={},
            error="Test execution failed"
        )

    # Thresholds - allow initial colorization frames
    UNEXPECTED_CHANGE_THRESHOLD = 0  # After initial frames, no changes

    unexpected = result.get("unexpected_changes", 999)
    passed = unexpected <= UNEXPECTED_CHANGE_THRESHOLD

    return TestResult(
        name="bg_stability",
        passed=passed,
        details=result,
        error=None if passed else f"Detected {unexpected} unexpected BG changes after stabilization"
    )


def run_performance_test(
    rom_path: str,
    savestate_path: Optional[str] = None
) -> TestResult:
    """Run performance test to detect game slowdown."""
    print("Running performance test...")

    result = run_lua_test(
        rom_path,
        "performance_test.lua",
        "performance_report.json",
        savestate_path,
        timeout_seconds=120  # 10 seconds of game time + overhead
    )

    if result is None:
        return TestResult(
            name="performance",
            passed=False,
            details={},
            error="Test execution failed"
        )

    # Thresholds
    TIME_RATIO_THRESHOLD = 1.15  # Max 15% slower than expected

    time_ratio = result.get("time_ratio", 999)
    passed = time_ratio <= TIME_RATIO_THRESHOLD

    return TestResult(
        name="performance",
        passed=passed,
        details=result,
        error=None if passed else f"Time ratio {time_ratio:.2f} exceeds threshold {TIME_RATIO_THRESHOLD}"
    )


def verify_rom(
    rom_path: str,
    savestate_path: Optional[str] = None,
    skip_performance: bool = False
) -> VerificationReport:
    """
    Run full verification suite on a ROM.

    Args:
        rom_path: Path to the ROM file
        savestate_path: Optional savestate to load
        skip_performance: Skip the performance test (runs for 10+ seconds)

    Returns:
        VerificationReport with all test results
    """
    results = []

    # Run stability tests
    results.append(run_oam_stability_test(rom_path, savestate_path))
    results.append(run_bg_stability_test(rom_path, savestate_path))

    # Performance test is optional (takes longer)
    if not skip_performance:
        results.append(run_performance_test(rom_path, savestate_path))

    # Overall pass/fail
    all_passed = all(r.passed for r in results)

    return VerificationReport(
        passed=all_passed,
        results=results,
        rom_path=rom_path,
        savestate_path=savestate_path
    )


def print_report(report: VerificationReport) -> None:
    """Print a formatted verification report."""
    print("\n" + "=" * 60)
    print("COLORIZATION VERIFICATION REPORT")
    print("=" * 60)
    print(f"ROM: {report.rom_path}")
    if report.savestate_path:
        print(f"Savestate: {report.savestate_path}")
    print()

    for result in report.results:
        status = "PASS" if result.passed else "FAIL"
        print(f"[{status}] {result.name}")

        if result.error:
            print(f"       Error: {result.error}")

        # Print key details based on test type
        details = result.details
        if result.name == "oam_stability":
            print(f"       Frames tested: {details.get('test_frames', '?')}")
            print(f"       Flicker count: {details.get('flicker_count', '?')}")
            print(f"       Sara flickers: {details.get('sara_flicker_count', '?')}")
            print(f"       Tile oscillations: {details.get('tile_oscillation_count', '?')}")

            # Show flicker events if any
            events = details.get("flicker_events", [])
            if events:
                print(f"       First flickers:")
                for evt in events[:5]:
                    print(f"         Frame {evt['frame']}: slot {evt['slot']} "
                          f"tile 0x{evt['tile']:02X} pal {evt['old_pal']} -> {evt['new_pal']}")

        elif result.name == "bg_stability":
            print(f"       Frames tested: {details.get('test_frames', '?')}")
            print(f"       Total changes: {details.get('total_changes', '?')}")
            print(f"       Unexpected changes: {details.get('unexpected_changes', '?')}")
            print(f"       Stabilization frame: {details.get('stabilization_frame', '?')}")

        elif result.name == "performance":
            print(f"       Expected time: {details.get('expected_time_seconds', '?'):.2f}s")
            print(f"       Actual time: {details.get('actual_time_seconds', '?'):.2f}s")
            print(f"       Time ratio: {details.get('time_ratio', '?'):.3f}")
            print(f"       Actual FPS: {details.get('actual_fps', '?'):.2f}")
            print(f"       Stutter frames: {details.get('stutter_frames', '?')}")

        print()

    print("=" * 60)
    if report.passed:
        print("OVERALL: PASS - All tests passed")
    else:
        failed_tests = [r.name for r in report.results if not r.passed]
        print(f"OVERALL: FAIL - Failed tests: {', '.join(failed_tests)}")
    print("=" * 60)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Automated colorization verification for Penta Dragon DX"
    )
    parser.add_argument(
        "rom_path",
        nargs="?",
        default="rom/working/penta_dragon_dx_FIXED.gb",
        help="Path to the ROM file"
    )
    parser.add_argument(
        "--savestate", "-t",
        help="Path to savestate file to load"
    )
    parser.add_argument(
        "--skip-performance",
        action="store_true",
        help="Skip performance test (saves time)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()

    # Resolve paths
    rom_path = Path(args.rom_path)
    if not rom_path.is_absolute():
        rom_path = PROJECT_ROOT / rom_path

    if not rom_path.exists():
        print(f"ERROR: ROM not found: {rom_path}", file=sys.stderr)
        sys.exit(1)

    savestate_path = None
    if args.savestate:
        savestate_path = Path(args.savestate)
        if not savestate_path.is_absolute():
            savestate_path = PROJECT_ROOT / savestate_path
        if not savestate_path.exists():
            print(f"ERROR: Savestate not found: {savestate_path}", file=sys.stderr)
            sys.exit(1)
        savestate_path = str(savestate_path)

    # Run verification
    report = verify_rom(
        str(rom_path),
        savestate_path,
        skip_performance=args.skip_performance
    )

    # Output results
    if args.json:
        output = {
            "passed": report.passed,
            "rom_path": report.rom_path,
            "savestate_path": report.savestate_path,
            "results": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "error": r.error,
                    "details": r.details
                }
                for r in report.results
            ]
        }
        print(json.dumps(output, indent=2))
    else:
        print_report(report)

    # Exit with appropriate code
    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
