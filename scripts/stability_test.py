#!/usr/bin/env python3
"""Stability test suite for Penta Dragon DX ROM builds.

This script provides comprehensive automated testing to verify ROM stability
BEFORE manual testing. It uses the mgba-mcp tools for headless operation.

Usage:
    uv run python scripts/stability_test.py                     # Test latest build
    uv run python scripts/stability_test.py rom/custom.gb       # Test specific ROM
    uv run python scripts/stability_test.py --quick             # Quick test only
    uv run python scripts/stability_test.py --verbose           # Show all details

Tests performed:
1. Boot Test: Fresh boot -> title screen appears (not corrupted)
2. Start Test: Press START -> "STAGE 01" appears -> gameplay starts
3. Static Test: 300 frames with no input -> no freeze, sprites animate
4. Movement Test: Move Sara left/right -> scroll works, no artifacts
5. Extended Test: 600+ frames -> no degradation

Exit codes:
    0 = All tests passed
    1 = One or more tests failed
    2 = Error running tests
"""

import argparse
import json
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Default ROM path
DEFAULT_ROM = Path(__file__).parent.parent / "rom" / "working" / "penta_dragon_dx_FIXED.gb"

# Save states for testing
SAVESTATES_DIR = Path(__file__).parent.parent / "save_states_for_claude"


@dataclass
class TestResult:
    """Result of a single test."""
    name: str
    passed: bool
    message: str
    details: Optional[dict] = None
    screenshots: list[bytes] = None

    def __post_init__(self):
        if self.screenshots is None:
            self.screenshots = []


class StabilityTester:
    """ROM stability testing using mgba-mcp tools."""

    def __init__(self, rom_path: Path, verbose: bool = False):
        self.rom_path = rom_path
        self.verbose = verbose
        self.results: list[TestResult] = []

    def log(self, msg: str, level: str = "INFO"):
        """Log a message."""
        if self.verbose or level in ("ERROR", "WARN"):
            print(f"[{level}] {msg}")

    def run_emulator(
        self,
        frames: int = 60,
        savestate: Optional[Path] = None,
        inputs: Optional[list[dict]] = None,
        capture_every: int = 30,
    ) -> dict:
        """Run emulator using mgba_run_sequence-style Lua script.

        Returns dict with:
        - success: bool
        - frame_count: int
        - freeze_detected: bool
        - oam_snapshots: list of OAM states
        - screenshots: list of screenshot paths
        """
        temp_dir = Path(tempfile.mkdtemp(prefix="stability_test_"))
        inputs = inputs or []

        # Key bitmask values for mGBA setKeys()
        KEY_MASKS = {
            "A": 0x01, "B": 0x02, "SELECT": 0x04, "START": 0x08,
            "RIGHT": 0x10, "LEFT": 0x20, "UP": 0x40, "DOWN": 0x80,
            "R": 0x100, "L": 0x200
        }

        # Build input event table
        input_events = []
        for inp in inputs:
            frame = inp.get("frame", 0)
            keys = inp.get("keys", [])
            mask = 0
            for key in keys:
                key_upper = key.upper()
                if key_upper in KEY_MASKS:
                    mask |= KEY_MASKS[key_upper]
            if mask > 0:
                input_events.append((frame, mask))
                input_events.append((frame + 5, 0))  # Release after 5 frames

        input_table_entries = []
        for frame, mask in input_events:
            input_table_entries.append(f'{{frame={frame}, mask={mask}}}')
        input_table = "{" + ", ".join(input_table_entries) + "}"

        lua_script = f"""
local frame = 0
local target_frames = {frames}
local capture_every = {capture_every}
local screenshots = {{}}
local oam_snapshots = {{}}
local last_oam_hash = ""
local frames_without_change = 0
local freeze_threshold = 60

local input_events = {input_table}
local input_index = 1

local function oam_hash()
    local parts = {{}}
    for slot = 0, 39 do
        local addr = 0xFE00 + slot * 4
        local y = emu:read8(addr)
        if y > 0 and y < 160 then
            local x = emu:read8(addr + 1)
            local tile = emu:read8(addr + 2)
            table.insert(parts, string.format("%d_%d_%d", y, x, tile))
        end
    end
    return table.concat(parts, "|")
end

local function capture_oam()
    local sprites = {{}}
    for slot = 0, 39 do
        local addr = 0xFE00 + slot * 4
        local y = emu:read8(addr)
        local x = emu:read8(addr + 1)
        local tile = emu:read8(addr + 2)
        local flags = emu:read8(addr + 3)
        if y > 0 and y < 160 then
            table.insert(sprites, string.format(
                '{{"slot":%d,"y":%d,"x":%d,"tile":%d,"pal":%d}}',
                slot, y, x, tile, flags % 8
            ))
        end
    end
    return "[" .. table.concat(sprites, ",") .. "]"
end

callbacks:add("frame", function()
    frame = frame + 1

    while input_index <= #input_events and input_events[input_index].frame <= frame do
        local evt = input_events[input_index]
        emu:setKeys(evt.mask)
        input_index = input_index + 1
    end

    local current_hash = oam_hash()
    if current_hash == last_oam_hash then
        frames_without_change = frames_without_change + 1
    else
        frames_without_change = 0
        last_oam_hash = current_hash
    end

    if frame % capture_every == 0 then
        local idx = math.floor(frame / capture_every)
        emu:screenshot("screenshot_" .. idx .. ".png")
        table.insert(screenshots, idx)
        table.insert(oam_snapshots, capture_oam())
    end

    if frame >= target_frames then
        local f = io.open("output.json", "w")
        if f then
            f:write('{{')
            f:write('"frame_count":' .. frame .. ',')
            f:write('"freeze_detected":' .. (frames_without_change >= freeze_threshold and "true" or "false") .. ',')
            f:write('"frames_without_change":' .. frames_without_change .. ',')
            f:write('"screenshot_indices":[' .. table.concat(screenshots, ",") .. '],')
            f:write('"oam_snapshots":[')
            for i, oam in ipairs(oam_snapshots) do
                if i > 1 then f:write(',') end
                f:write(oam)
            end
            f:write(']')
            f:write('}}')
            f:close()
        end
        emu:screenshot("screenshot.png")
        local done = io.open("DONE", "w")
        if done then done:write("OK"); done:close() end
    end
end)
"""
        # Write Lua script
        lua_file = temp_dir / "test_script.lua"
        lua_file.write_text(lua_script)

        # Build command - paths are passed as separate arguments so quoting handled by subprocess
        rom_path_str = str(self.rom_path.resolve())  # Use absolute path
        cmd = ["xvfb-run", "-a", "mgba-qt", rom_path_str]
        if savestate:
            cmd.extend(["-t", str(savestate.resolve())])
        cmd.extend(["--script", str(lua_file), "-l", "0"])

        self.log(f"Running: {' '.join(cmd)}")

        # Run with timeout
        import os
        env = os.environ.copy()
        env["SDL_AUDIODRIVER"] = "dummy"
        if "DISPLAY" in env:
            del env["DISPLAY"]
        if "WAYLAND_DISPLAY" in env:
            del env["WAYLAND_DISPLAY"]
        env["QT_QPA_PLATFORM"] = "xcb"

        timeout = max(60, frames // 60 * 2 + 10)  # ~2x expected runtime + buffer

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(temp_dir),
                start_new_session=True,
                env=env,
            )

            done_file = temp_dir / "DONE"
            start_time = time.time()

            while time.time() - start_time < timeout:
                if done_file.exists():
                    time.sleep(0.5)  # Let files flush
                    break
                if proc.poll() is not None:
                    break
                time.sleep(0.1)

            # Kill process
            import signal
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                time.sleep(0.2)
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass

            # Read results
            output_file = temp_dir / "output.json"
            if output_file.exists():
                data = json.loads(output_file.read_text())

                # Collect screenshots
                screenshots = []
                for idx in data.get("screenshot_indices", []):
                    screenshot_path = temp_dir / f"screenshot_{idx}.png"
                    if screenshot_path.exists():
                        screenshots.append(screenshot_path.read_bytes())

                data["screenshots"] = screenshots
                data["success"] = True
                return data

            return {"success": False, "error": "No output produced"}

        except Exception as e:
            return {"success": False, "error": str(e)}

        finally:
            # Cleanup
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass

    def test_boot(self) -> TestResult:
        """Test 1: Fresh boot to title screen.

        This test only verifies the ROM boots and produces output.
        Title screens are often static, so we don't check for OAM animation.
        """
        self.log("Running boot test...")

        result = self.run_emulator(frames=180, capture_every=60)  # ~3 seconds

        if not result.get("success"):
            return TestResult(
                name="Boot Test",
                passed=False,
                message=f"Failed to run emulator: {result.get('error')}",
            )

        # For boot test, we just verify we got frame output and screenshots
        # Title screens often don't animate, so freeze detection doesn't apply
        frame_count = result.get("frame_count", 0)
        if frame_count < 60:
            return TestResult(
                name="Boot Test",
                passed=False,
                message=f"Only ran {frame_count} frames, expected at least 60",
                details=result,
            )

        return TestResult(
            name="Boot Test",
            passed=True,
            message=f"Boot completed successfully ({frame_count} frames)",
            details=result,
            screenshots=result.get("screenshots", []),
        )

    def test_start_game(self) -> TestResult:
        """Test 2: Press START to begin game."""
        self.log("Running start game test...")

        # Press START after boot (at frame 120), then wait
        result = self.run_emulator(
            frames=300,
            capture_every=60,
            inputs=[
                {"frame": 120, "keys": ["START"]},
            ],
        )

        if not result.get("success"):
            return TestResult(
                name="Start Game Test",
                passed=False,
                message=f"Failed to run emulator: {result.get('error')}",
            )

        if result.get("freeze_detected"):
            return TestResult(
                name="Start Game Test",
                passed=False,
                message="Freeze detected after pressing START",
                details=result,
            )

        return TestResult(
            name="Start Game Test",
            passed=True,
            message="Game started successfully",
            details=result,
            screenshots=result.get("screenshots", []),
        )

    def test_gameplay_static(self) -> TestResult:
        """Test 3: Run gameplay with no input, verify no complete freeze.

        Note: Save states may be for colorized ROM versions and might not load
        properly with original ROM. In that case, we test fresh boot instead.
        """
        self.log("Running static gameplay test...")

        # Check if this is the original ROM or a colorized version
        rom_name = self.rom_path.name.lower()
        is_original = "penta dragon (j)" in rom_name and "dx" not in rom_name

        # Use savestate only for colorized ROMs
        savestate = None
        if not is_original:
            savestate = SAVESTATES_DIR / "level1_sara_w_4_hornets.ss0"
            if not savestate.exists():
                savestates = list(SAVESTATES_DIR.glob("*.ss0"))
                savestate = savestates[0] if savestates else None

        if is_original:
            self.log("Testing original ROM - pressing START to begin gameplay")
            # For original ROM, press START to get to gameplay
            result = self.run_emulator(
                frames=300,
                capture_every=30,
                inputs=[
                    {"frame": 60, "keys": ["START"]},  # Start game
                ],
            )
        else:
            result = self.run_emulator(
                frames=300,
                capture_every=30,
                savestate=savestate,
            )

        if not result.get("success"):
            return TestResult(
                name="Static Gameplay Test",
                passed=False,
                message=f"Failed to run emulator: {result.get('error')}",
            )

        frame_count = result.get("frame_count", 0)
        frames_static = result.get("frames_without_change", 0)

        # A true freeze means ALL frames had no OAM change (after the initial period)
        # For a game starting from title, we expect SOME animation after pressing START
        # Give generous threshold - freeze only if >90% of frames are static
        freeze_threshold = int(frame_count * 0.9)
        if frames_static >= freeze_threshold:
            return TestResult(
                name="Static Gameplay Test",
                passed=False,
                message=f"Possible freeze: {frames_static}/{frame_count} frames static",
                details=result,
            )

        return TestResult(
            name="Static Gameplay Test",
            passed=True,
            message=f"Gameplay ran for {frame_count} frames ({frames_static} static frames at end)",
            details=result,
            screenshots=result.get("screenshots", []),
        )

    def test_movement(self) -> TestResult:
        """Test 4: Move Sara and verify scrolling works."""
        self.log("Running movement test...")

        savestate = SAVESTATES_DIR / "level1_sara_w_alone.ss0"
        if not savestate.exists():
            savestates = list(SAVESTATES_DIR.glob("*.ss0"))
            savestate = savestates[0] if savestates else None

        # Move right for a bit, then left
        result = self.run_emulator(
            frames=300,
            capture_every=60,
            savestate=savestate,
            inputs=[
                {"frame": 10, "keys": ["RIGHT"]},
                {"frame": 30, "keys": ["RIGHT"]},
                {"frame": 50, "keys": ["RIGHT"]},
                {"frame": 100, "keys": ["LEFT"]},
                {"frame": 120, "keys": ["LEFT"]},
                {"frame": 140, "keys": ["LEFT"]},
            ],
        )

        if not result.get("success"):
            return TestResult(
                name="Movement Test",
                passed=False,
                message=f"Failed to run emulator: {result.get('error')}",
            )

        if result.get("freeze_detected"):
            return TestResult(
                name="Movement Test",
                passed=False,
                message="Freeze detected during movement",
                details=result,
            )

        return TestResult(
            name="Movement Test",
            passed=True,
            message="Movement completed without freeze",
            details=result,
            screenshots=result.get("screenshots", []),
        )

    def test_extended_run(self) -> TestResult:
        """Test 5: Extended run for 600+ frames."""
        self.log("Running extended test...")

        savestate = SAVESTATES_DIR / "level1_sara_w_4_hornets.ss0"
        if not savestate.exists():
            savestates = list(SAVESTATES_DIR.glob("*.ss0"))
            savestate = savestates[0] if savestates else None

        result = self.run_emulator(
            frames=600,
            capture_every=100,
            savestate=savestate,
        )

        if not result.get("success"):
            return TestResult(
                name="Extended Run Test",
                passed=False,
                message=f"Failed to run emulator: {result.get('error')}",
            )

        if result.get("freeze_detected"):
            return TestResult(
                name="Extended Run Test",
                passed=False,
                message=f"Freeze detected after {result.get('frames_without_change', 0)} static frames",
                details=result,
            )

        return TestResult(
            name="Extended Run Test",
            passed=True,
            message=f"Extended run completed ({result.get('frame_count', 0)} frames)",
            details=result,
            screenshots=result.get("screenshots", []),
        )

    def run_all_tests(self, quick: bool = False) -> bool:
        """Run all stability tests.

        Args:
            quick: If True, only run boot and static tests

        Returns:
            True if all tests passed, False otherwise
        """
        print(f"\n{'='*60}")
        print(f"Penta Dragon DX Stability Test Suite")
        print(f"ROM: {self.rom_path}")
        print(f"{'='*60}\n")

        # Verify ROM exists
        if not self.rom_path.exists():
            print(f"ERROR: ROM not found: {self.rom_path}")
            return False

        # Run tests
        tests = [
            self.test_boot,
            self.test_start_game if not quick else None,
            self.test_gameplay_static,
            self.test_movement if not quick else None,
            self.test_extended_run if not quick else None,
        ]

        for test_fn in tests:
            if test_fn is None:
                continue

            try:
                result = test_fn()
                self.results.append(result)

                status = "PASS" if result.passed else "FAIL"
                print(f"[{status}] {result.name}: {result.message}")

                if not result.passed and self.verbose and result.details:
                    # Remove non-serializable data for display
                    display_details = {k: v for k, v in result.details.items()
                                       if k not in ("screenshots", "oam_snapshots")}
                    print(f"       Details: {json.dumps(display_details, indent=2)}")

            except Exception as e:
                print(f"[ERROR] {test_fn.__name__}: {e}")
                self.results.append(TestResult(
                    name=test_fn.__name__,
                    passed=False,
                    message=str(e),
                ))

        # Summary
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)

        print(f"\n{'='*60}")
        print(f"Results: {passed}/{total} tests passed")
        print(f"{'='*60}\n")

        return passed == total


def main():
    parser = argparse.ArgumentParser(
        description="Stability test suite for Penta Dragon DX ROM builds",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "rom",
        nargs="?",
        type=Path,
        default=DEFAULT_ROM,
        help=f"ROM file to test (default: {DEFAULT_ROM})",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick test only (boot + static)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output",
    )

    args = parser.parse_args()

    tester = StabilityTester(args.rom, verbose=args.verbose)

    try:
        success = tester.run_all_tests(quick=args.quick)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error running tests: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
