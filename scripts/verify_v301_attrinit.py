#!/usr/bin/env python3
"""Verify attr-cleaner ROM eliminates VRAM bank-1 0xFF (uninit) attrs.

Compares production v3.01 ROM vs attrinit variant.

For each ROM, runs an mGBA Lua probe that:
  - Auto-navigates title menu (no SELECT — we want pristine cold-boot
    behavior plus normal gameplay entry).
  - Samples VRAM bank 1 attrs over both 0x9800 and 0x9C00 tilemap
    regions (1024 bytes each = 2048 bytes total).
  - Counts uninit (0xFF) and non-zero attr bytes at frames 200, 400, 1200.
  - At f=1200 captures a screenshot (matches SELECT-menu probing window).

Writes JSON results to tmp/attrinit/<rom_name>_attrs.json.

Then prints a side-by-side comparison.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path


PROBE_LUA = r"""
local SAMPLES = {200, 400, 1200}
local SCREENSHOT_AT = 1200
local OUT = os.getenv("PROBE_OUT")
local SHOT = os.getenv("PROBE_SHOT")

local KEY_A = 0x01
local KEY_START = 0x08
local KEY_DOWN = 0x80
local TITLE = {
    {180, 185, KEY_DOWN}, {193, 198, KEY_A}, {241, 246, KEY_A},
    {291, 296, KEY_A}, {341, 346, KEY_START}, {391, 396, KEY_A},
}

local f = 0
local results = {}
local done = false

local function sample_attrs(region_base)
    -- region_base = 0x9800 or 0x9C00
    -- Returns: total bytes, uninit (0xFF) count, nonzero count
    emu:write8(0xFF4F, 1)
    local total = 0
    local uninit = 0
    local nonzero = 0
    for addr = region_base, region_base + 0x3FF do
        local b = emu:read8(addr)
        total = total + 1
        if b == 0xFF then uninit = uninit + 1 end
        if b ~= 0 then nonzero = nonzero + 1 end
    end
    emu:write8(0xFF4F, 0)
    return total, uninit, nonzero
end

callbacks:add("frame", function()
    if done then return end
    f = f + 1

    -- Auto-nav title
    if f <= 500 then
        local k = 0
        for _, e in ipairs(TITLE) do
            if f >= e[1] and f <= e[2] then k = e[3]; break end
        end
        emu:setKeys(k)
    else
        emu:setKeys(0)
    end

    -- Sample at target frames
    for _, sf in ipairs(SAMPLES) do
        if f == sf then
            local t98, u98, n98 = sample_attrs(0x9800)
            local t9c, u9c, n9c = sample_attrs(0x9C00)
            local lcdc = emu:read8(0xFF40)
            local displayed = (lcdc & 0x08) ~= 0 and "0x9C00" or "0x9800"
            local df02 = emu:read8(0xDF02)
            local df07 = emu:read8(0xDF07)
            local df08 = emu:read8(0xDF08)
            local ffc1 = emu:read8(0xFFC1)
            results[#results + 1] = {
                frame = f, lcdc = lcdc, displayed = displayed,
                df02 = df02, df07 = df07, df08 = df08, ffc1 = ffc1,
                tilemap_9800 = {total = t98, uninit_ff = u98, nonzero = n98},
                tilemap_9C00 = {total = t9c, uninit_ff = u9c, nonzero = n9c},
            }
        end
    end

    if f == SCREENSHOT_AT then
        emu:screenshot(SHOT)
    end

    if f >= SAMPLES[#SAMPLES] + 30 then
        -- Write JSON manually (mGBA Lua has no json lib)
        local fh = io.open(OUT, "w")
        fh:write("[\n")
        for i, r in ipairs(results) do
            fh:write(string.format(
                '  {"frame":%d,"lcdc":%d,"displayed":"%s","df02":%d,"df07":%d,"df08":%d,"ffc1":%d,' ..
                '"t9800":{"total":%d,"uninit_ff":%d,"nonzero":%d},' ..
                '"t9C00":{"total":%d,"uninit_ff":%d,"nonzero":%d}}%s\n',
                r.frame, r.lcdc, r.displayed, r.df02, r.df07, r.df08, r.ffc1,
                r.tilemap_9800.total, r.tilemap_9800.uninit_ff, r.tilemap_9800.nonzero,
                r.tilemap_9C00.total, r.tilemap_9C00.uninit_ff, r.tilemap_9C00.nonzero,
                (i < #results) and "," or ""
            ))
        end
        fh:write("]\n")
        fh:close()
        done = true
    end
end)
"""


def _clean_x_locks():
    """Remove leftover X locks that block xvfb-run from grabbing a display.
    Only removes files we own. Best-effort; does not raise on permission errors.
    """
    for entry in Path("/tmp").glob(".X*-lock"):
        try:
            if entry.is_file():
                entry.unlink()
        except (PermissionError, FileNotFoundError):
            pass


def probe(rom_path: Path, out_dir: Path) -> dict:
    """Run mGBA Lua probe on rom_path, return parsed results."""
    name = rom_path.stem
    probe_out = out_dir / f"{name}_attrs.json"
    probe_shot = out_dir / f"{name}_f1200.png"

    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False) as luaf:
        luaf.write(PROBE_LUA)
        lua_path = Path(luaf.name)

    try:
        env = {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", "/tmp"),
            "PROBE_OUT": str(probe_out),
            "PROBE_SHOT": str(probe_shot),
            "QT_QPA_PLATFORM": "offscreen",
            "SDL_AUDIODRIVER": "dummy",
        }

        _clean_x_locks()

        proc = subprocess.Popen(
            ["xvfb-run", "-a", "mgba-qt", str(rom_path), "--script", str(lua_path)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.time() + 60
            while time.time() < deadline:
                if probe_out.exists() and probe_out.stat().st_size > 0:
                    time.sleep(0.5)  # let final fh:write flush
                    break
                time.sleep(0.5)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
            _clean_x_locks()
    finally:
        lua_path.unlink(missing_ok=True)

    if not probe_out.exists():
        return {"error": "probe did not produce output", "rom": str(rom_path)}

    try:
        data = json.loads(probe_out.read_text())
    except json.JSONDecodeError as e:
        return {"error": f"json decode failed: {e}", "raw": probe_out.read_text()}
    return {
        "rom": str(rom_path),
        "out_json": str(probe_out),
        "screenshot": str(probe_shot) if probe_shot.exists() else None,
        "screenshot_size": probe_shot.stat().st_size if probe_shot.exists() else 0,
        "samples": data,
    }


def main():
    out_dir = Path("tmp/attrinit")
    out_dir.mkdir(parents=True, exist_ok=True)

    roms = [
        Path("rom/working/penta_dragon_dx_v301.gb"),
        Path("rom/working/penta_dragon_dx_v301_attrinit.gb"),
    ]

    results = {}
    for rom in roms:
        if not rom.exists():
            print(f"SKIP: {rom} not found")
            continue
        print(f"Probing {rom}...")
        results[rom.name] = probe(rom, out_dir)

    # Print comparison
    print("\n" + "=" * 78)
    print("VRAM bank-1 attr uninit (0xFF) count comparison")
    print("=" * 78)
    print(f"{'frame':>6} | {'tilemap':>8} | {'displayed':>10} | "
          f"{'v301 uninit':>11} | {'attrinit uninit':>15} | {'delta':>6}")
    print("-" * 78)

    prod = results.get("penta_dragon_dx_v301.gb", {}).get("samples", [])
    aii = results.get("penta_dragon_dx_v301_attrinit.gb", {}).get("samples", [])

    by_frame_prod = {s["frame"]: s for s in prod}
    by_frame_aii = {s["frame"]: s for s in aii}

    for frame in sorted(set(by_frame_prod) | set(by_frame_aii)):
        p = by_frame_prod.get(frame, {})
        a = by_frame_aii.get(frame, {})
        for tm in ["t9800", "t9C00"]:
            pv = p.get(tm, {}).get("uninit_ff", "—")
            av = a.get(tm, {}).get("uninit_ff", "—")
            displayed_prod = p.get("displayed", "?")
            displayed_aii = a.get("displayed", "?")
            is_displayed = ""
            tm_addr = "0x9800" if tm == "t9800" else "0x9C00"
            if isinstance(pv, int) and isinstance(av, int):
                delta = av - pv
                delta_str = f"{delta:+d}"
            else:
                delta_str = "?"
            disp_marker = ""
            if displayed_aii == tm_addr:
                disp_marker = " <"
            print(f"{frame:>6} | {tm_addr:>8} | {displayed_aii:>10} | "
                  f"{pv:>11} | {av:>15} | {delta_str:>6}{disp_marker}")

    print("\nDF07 (attr cleaner row counter) trajectory (attrinit only):")
    for s in aii:
        print(f"  f={s['frame']:>5}  DF07={s['df07']:>3}  DF08={s['df08']:#04x}  "
              f"FFC1={s['ffc1']}  DF02={s['df02']:#04x}")

    print(f"\nScreenshots:")
    for rom_name, r in results.items():
        if r.get("screenshot"):
            print(f"  {rom_name}: {r['screenshot']} ({r['screenshot_size']} bytes)")

    # Pass/fail summary
    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)
    if aii and prod:
        # Total uninit at last frame
        last_aii = aii[-1] if aii else None
        last_prod = prod[-1] if prod else None
        if last_aii and last_prod:
            total_prod = last_prod["t9800"]["uninit_ff"] + last_prod["t9C00"]["uninit_ff"]
            total_aii = last_aii["t9800"]["uninit_ff"] + last_aii["t9C00"]["uninit_ff"]
            print(f"  Frame {last_aii['frame']} total uninit (both tilemaps):")
            print(f"    v3.01 production: {total_prod}")
            print(f"    v3.01 attrinit:   {total_aii}")
            improvement = total_prod - total_aii
            print(f"    delta:            {-improvement:+d}")
            if total_aii < total_prod:
                print(f"  PASS: attrinit reduces uninit attrs by {improvement}")
                return 0
            else:
                print("  FAIL: attrinit did not reduce uninit attrs")
                return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
