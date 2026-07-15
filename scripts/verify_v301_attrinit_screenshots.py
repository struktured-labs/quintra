#!/usr/bin/env python3
"""Capture screenshots at multiple frames for side-by-side comparison.

Frames captured:
  f=100   — title screen (animated draw in progress)
  f=200   — title screen (after cold-boot cleaner finishes)
  f=400   — STAGE 01 splash / gameplay transition
  f=1200  — gameplay scene matching SELECT-menu probe timing

Runs both v3.01 production and attrinit, dumps PNGs to tmp/attrinit/shots/.
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


PROBE_LUA = r"""
local FRAMES = {100, 200, 400, 1200}
local SHOT_BASE = os.getenv("SHOT_BASE")
local KEY_A=0x01; local KEY_START=0x08; local KEY_DOWN=0x80
local TITLE = {
    {180,185,KEY_DOWN},{193,198,KEY_A},{241,246,KEY_A},
    {291,296,KEY_A},{341,346,KEY_START},{391,396,KEY_A},
}
local f = 0
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
        emu:setKeys(0)
    end
    for _, sf in ipairs(FRAMES) do
        if f == sf then
            emu:screenshot(string.format("%s_f%04d.png", SHOT_BASE, sf))
        end
    end
    if f >= FRAMES[#FRAMES] + 30 then
        -- write sentinel so caller knows we're done
        local fh = io.open(SHOT_BASE .. "_done.txt", "w")
        fh:write("done\n")
        fh:close()
        done = true
    end
end)
"""


def _clean_x_locks():
    for entry in Path("/tmp").glob(".X*-lock"):
        try:
            if entry.is_file(): entry.unlink()
        except (PermissionError, FileNotFoundError):
            pass


def capture(rom_path: Path, shot_base: Path):
    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False) as luaf:
        luaf.write(PROBE_LUA)
        lua_path = Path(luaf.name)
    done_marker = Path(str(shot_base) + "_done.txt")
    done_marker.unlink(missing_ok=True)
    try:
        env = {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", "/tmp"),
            "SHOT_BASE": str(shot_base),
            "QT_QPA_PLATFORM": "offscreen", "SDL_AUDIODRIVER": "dummy",
        }
        _clean_x_locks()
        proc = subprocess.Popen(
            ["xvfb-run", "-a", "mgba-qt", str(rom_path), "--script", str(lua_path)],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.time() + 60
            while time.time() < deadline:
                if done_marker.exists():
                    time.sleep(0.5); break
                time.sleep(0.5)
        finally:
            proc.terminate()
            try: proc.wait(timeout=3)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait(timeout=3)
            _clean_x_locks()
    finally:
        lua_path.unlink(missing_ok=True)


def main():
    out_dir = Path("tmp/attrinit/shots")
    out_dir.mkdir(parents=True, exist_ok=True)
    for rom in [
        Path("rom/working/penta_dragon_dx_v301.gb"),
        Path("rom/working/penta_dragon_dx_v301_attrinit.gb"),
    ]:
        if not rom.exists():
            print(f"SKIP: {rom}"); continue
        shot_base = out_dir / rom.stem
        print(f"Capturing {rom} → {shot_base}_fXXXX.png")
        capture(rom, shot_base)
    print(f"\nShots in {out_dir}:")
    for p in sorted(out_dir.glob("*.png")):
        print(f"  {p} ({p.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
