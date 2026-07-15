#!/usr/bin/env python3
"""Dump attr values at f100 to understand what attrs are needed for title."""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROBE_LUA = r"""
local SAMPLES = {100, 200}
local OUT = os.getenv("PROBE_OUT")
local KEY_A=0x01; local KEY_START=0x08; local KEY_DOWN=0x80
local TITLE = {
    {180,185,KEY_DOWN},{193,198,KEY_A},{241,246,KEY_A},
    {291,296,KEY_A},{341,346,KEY_START},{391,396,KEY_A},
}
local f = 0
local results = {}
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
    end
    for _, sf in ipairs(SAMPLES) do
        if f == sf then
            -- Read both VBK=0 (tile IDs) and VBK=1 (attrs)
            emu:write8(0xFF4F, 0)
            local tiles = {}
            for r = 0, 31 do
                local row = {}
                for c = 0, 31 do
                    row[c+1] = emu:read8(0x9800 + r * 32 + c)
                end
                tiles[r+1] = row
            end
            emu:write8(0xFF4F, 1)
            local attrs = {}
            for r = 0, 31 do
                local row = {}
                for c = 0, 31 do
                    row[c+1] = emu:read8(0x9800 + r * 32 + c)
                end
                attrs[r+1] = row
            end
            emu:write8(0xFF4F, 0)
            results[#results + 1] = {frame = f, tiles = tiles, attrs = attrs}
        end
    end
    if f >= SAMPLES[#SAMPLES] + 30 then
        local fh = io.open(OUT, "w")
        fh:write("[\n")
        for i, r in ipairs(results) do
            local function rows_to_json(rows)
                local parts = {}
                for r_idx = 1, 32 do
                    local row = rows[r_idx]
                    local s = {}
                    for c_idx = 1, 32 do
                        s[c_idx] = string.format("%02X", row[c_idx])
                    end
                    parts[r_idx] = table.concat(s, ",")
                end
                return "[\"" .. table.concat(parts, "\",\"") .. "\"]"
            end
            fh:write(string.format(
                '  {"frame":%d,"tiles":%s,"attrs":%s}%s\n',
                r.frame, rows_to_json(r.tiles), rows_to_json(r.attrs),
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
    for entry in Path("/tmp").glob(".X*-lock"):
        try:
            if entry.is_file(): entry.unlink()
        except (PermissionError, FileNotFoundError):
            pass


def probe(rom_path, out_path):
    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False) as luaf:
        luaf.write(PROBE_LUA)
        lua_path = Path(luaf.name)
    try:
        env = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
               "HOME": os.environ.get("HOME", "/tmp"),
               "PROBE_OUT": str(out_path),
               "QT_QPA_PLATFORM": "offscreen", "SDL_AUDIODRIVER": "dummy"}
        _clean_x_locks()
        proc = subprocess.Popen(["xvfb-run", "-a", "mgba-qt", str(rom_path), "--script", str(lua_path)],
                                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.time() + 60
            while time.time() < deadline:
                if out_path.exists() and out_path.stat().st_size > 0:
                    time.sleep(0.5); break
                time.sleep(0.5)
        finally:
            proc.terminate()
            try: proc.wait(timeout=3)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait(timeout=3)
            _clean_x_locks()
    finally:
        lua_path.unlink(missing_ok=True)
    return json.loads(out_path.read_text()) if out_path.exists() else []


def main():
    out_dir = Path("tmp/attrinit"); out_dir.mkdir(parents=True, exist_ok=True)
    for rom in [Path("rom/working/penta_dragon_dx_v301.gb"),
                Path("rom/working/penta_dragon_dx_v301_attrinit.gb")]:
        out_json = out_dir / f"{rom.stem}_f100_dump.json"
        print(f"=== {rom} ===")
        results = probe(rom, out_json)
        for s in results:
            f = s["frame"]
            print(f"\n--- f={f} ---")
            tiles = [row.split(",") for row in s["tiles"]]
            attrs = [row.split(",") for row in s["attrs"]]
            # Find rows with non-zero TILE IDs (active title area)
            for r_idx in range(20):
                if any(int(tiles[r_idx][c], 16) != 0 for c in range(32)):
                    line = []
                    line_attrs = []
                    for c_idx in range(32):
                        t = int(tiles[r_idx][c_idx], 16)
                        a = int(attrs[r_idx][c_idx], 16)
                        if t == 0:
                            line.append("..")
                            line_attrs.append("..")
                        else:
                            line.append(f"{t:02X}")
                            line_attrs.append(f"{a:02X}")
                    print(f"r{r_idx:>2} T: {' '.join(line)}")
                    print(f"r{r_idx:>2} A: {' '.join(line_attrs)}")


if __name__ == "__main__":
    main()
