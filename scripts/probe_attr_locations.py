#!/usr/bin/env python3
"""Where are the uninit (0xFF) attrs in VRAM bank 1 at f400 and f1200?

Captures full 32x32 attr map for both 0x9800 and 0x9C00 tilemaps, then
ASCII-renders a grid showing which positions hold 0xFF.

Helps narrow down whether splotches are in the viewport (rows 0-17,
cols 0-19) or off-screen (rows 18-31, cols 20-31), and whether they
cluster in specific patterns (e.g., HUD row, window-layer overlay).
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROBE_LUA = r"""
local SAMPLES = {400, 1200}
local OUT = os.getenv("PROBE_OUT")

local KEY_A=0x01; local KEY_START=0x08; local KEY_DOWN=0x80
local TITLE = {
    {180,185,KEY_DOWN},{193,198,KEY_A},{241,246,KEY_A},
    {291,296,KEY_A},{341,346,KEY_START},{391,396,KEY_A},
}

local f = 0
local results = {}
local done = false

local function dump_attrs(region_base)
    emu:write8(0xFF4F, 1)
    local rows = {}
    for r = 0, 31 do
        local row = {}
        for c = 0, 31 do
            local b = emu:read8(region_base + r * 32 + c)
            row[c + 1] = b
        end
        rows[r + 1] = row
    end
    emu:write8(0xFF4F, 0)
    return rows
end

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
    for _, sf in ipairs(SAMPLES) do
        if f == sf then
            results[#results + 1] = {
                frame = f,
                t9800 = dump_attrs(0x9800),
                t9C00 = dump_attrs(0x9C00),
            }
        end
    end
    if f >= SAMPLES[#SAMPLES] + 30 then
        local fh = io.open(OUT, "w")
        fh:write("[\n")
        for i, r in ipairs(results) do
            local function row_str(rows)
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
                '  {"frame":%d,"t9800":%s,"t9C00":%s}%s\n',
                r.frame, row_str(r.t9800), row_str(r.t9C00),
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


def probe(rom_path: Path, out_path: Path) -> list:
    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False) as luaf:
        luaf.write(PROBE_LUA)
        lua_path = Path(luaf.name)
    try:
        env = {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", "/tmp"),
            "PROBE_OUT": str(out_path),
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
    if not out_path.exists():
        return []
    try:
        return json.loads(out_path.read_text())
    except json.JSONDecodeError:
        return []


def render_grid(rows: list[str], label: str) -> str:
    lines = [f"{label} (32x32, '.' = 0x00, '#' = 0xFF, '+' = other)"]
    header = "    " + "".join(f"{i:01x}" for i in range(32))
    lines.append(header)
    for r_idx, row_str in enumerate(rows):
        row = [int(x, 16) for x in row_str.split(",")]
        cells = []
        for c_idx, b in enumerate(row):
            if b == 0: ch = "."
            elif b == 0xFF: ch = "#"
            else: ch = "+"
            cells.append(ch)
        viewport = " V" if 0 <= r_idx <= 17 else "  "
        lines.append(f"r{r_idx:>2}{viewport}{''.join(cells)}")
    return "\n".join(lines)


def main():
    out_dir = Path("tmp/attrinit")
    out_dir.mkdir(parents=True, exist_ok=True)

    for rom in [
        Path("rom/working/penta_dragon_dx_v301.gb"),
        Path("rom/working/penta_dragon_dx_v301_attrinit.gb"),
    ]:
        if not rom.exists():
            print(f"SKIP: {rom}"); continue
        out_json = out_dir / f"{rom.stem}_grid.json"
        print(f"\n\n{'=' * 78}\nROM: {rom}\n{'=' * 78}")
        results = probe(rom, out_json)
        for sample in results:
            f = sample["frame"]
            print(f"\n--- frame {f} ---")
            for tm_key, tm_label in [("t9800", "0x9800"), ("t9C00", "0x9C00")]:
                rows = sample[tm_key]
                # Count 0xFF
                count_ff = sum(1 for row in rows for x in row.split(",")
                               if int(x, 16) == 0xFF)
                count_other = sum(1 for row in rows for x in row.split(",")
                                  if int(x, 16) not in (0, 0xFF))
                print(f"\n{tm_label} (frame {f}): {count_ff} uninit, "
                      f"{count_other} non-default")
                if count_ff > 0:
                    print(render_grid(rows, f"  {tm_label}"))


if __name__ == "__main__":
    main()
