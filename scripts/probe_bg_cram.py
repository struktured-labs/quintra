#!/usr/bin/env python3
"""Compare BG CRAM (CGB BG palette RAM) at f100 between ROMs."""
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

PROBE_LUA = r"""
local SAMPLES = {100, 200, 400}
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
            -- Read 64 BG CRAM bytes via BCPS auto-increment
            local bg = {}
            for i = 0, 63 do
                emu:write8(0xFF68, 0x80 + i)
                bg[i+1] = emu:read8(0xFF69)
            end
            results[#results+1] = {frame = f, bg_cram = bg}
        end
    end
    if f >= SAMPLES[#SAMPLES] + 30 then
        local fh = io.open(OUT, "w")
        fh:write("[\n")
        for i, r in ipairs(results) do
            local s = {}
            for j, v in ipairs(r.bg_cram) do s[j] = string.format("%02X", v) end
            fh:write(string.format('  {"frame":%d,"bg":"%s"}%s\n',
                r.frame, table.concat(s, ","),
                (i < #results) and "," or ""))
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
        except (PermissionError, FileNotFoundError): pass


def probe(rom, out):
    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False) as luaf:
        luaf.write(PROBE_LUA); lua_path = Path(luaf.name)
    try:
        env = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
               "HOME": os.environ.get("HOME", "/tmp"), "PROBE_OUT": str(out),
               "QT_QPA_PLATFORM": "offscreen", "SDL_AUDIODRIVER": "dummy"}
        _clean_x_locks()
        proc = subprocess.Popen(["xvfb-run", "-a", "mgba-qt", str(rom), "--script", str(lua_path)],
                                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.time() + 60
            while time.time() < deadline:
                if out.exists() and out.stat().st_size > 0: time.sleep(0.5); break
                time.sleep(0.5)
        finally:
            proc.terminate()
            try: proc.wait(timeout=3)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait(timeout=3)
            _clean_x_locks()
    finally:
        lua_path.unlink(missing_ok=True)
    return json.loads(out.read_text()) if out.exists() else []


def main():
    out_dir = Path("tmp/attrinit"); out_dir.mkdir(parents=True, exist_ok=True)
    data = {}
    for rom in [Path("rom/working/penta_dragon_dx_v301.gb"),
                Path("rom/working/penta_dragon_dx_v301_attrinit.gb")]:
        out_json = out_dir / f"{rom.stem}_bg_cram.json"
        data[rom.name] = probe(rom, out_json)
    for fi in range(min(len(data["penta_dragon_dx_v301.gb"]), len(data["penta_dragon_dx_v301_attrinit.gb"]))):
        prod = data["penta_dragon_dx_v301.gb"][fi]
        aii = data["penta_dragon_dx_v301_attrinit.gb"][fi]
        f = prod["frame"]
        same = prod["bg"] == aii["bg"]
        print(f"f={f}: bg_cram {'SAME' if same else 'DIFFERENT'}")
        if not same:
            # Show byte-by-byte differences
            pb = prod["bg"].split(",")
            ab = aii["bg"].split(",")
            for j, (p, a) in enumerate(zip(pb, ab)):
                if p != a:
                    pal = j // 8
                    color = (j % 8) // 2
                    byte = j % 2
                    print(f"  byte {j} (pal {pal}, color {color}, {'lo' if byte == 0 else 'hi'}): prod={p} aii={a}")
            print(f"  prod: {prod['bg']}")
            print(f"  aii:  {aii['bg']}")


if __name__ == "__main__":
    main()
