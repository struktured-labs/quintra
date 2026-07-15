#!/usr/bin/env python3
"""Check OBJ CRAM at f100/f200 between v3.01 production and attrinit ROMs.

If title sprites use OBJ palettes, differences here would explain
the screenshot variance (some letters appearing fully colored vs
appearing transparent/missing).
"""
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

PROBE_LUA = r"""
local SAMPLES = {100, 200, 400, 1200}
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
            -- Read DMG palette regs + OBP
            local lcdc = emu:read8(0xFF40)
            local bgp = emu:read8(0xFF47)
            local obp0 = emu:read8(0xFF48)
            local obp1 = emu:read8(0xFF49)
            -- Read first 4 OBJ palettes (32 bytes via OCPS auto-increment)
            local obj = {}
            for i = 0, 31 do
                emu:write8(0xFF6A, 0x80 + i)
                obj[i+1] = emu:read8(0xFF6B)
            end
            -- Read OAM (first 8 sprites = 32 bytes)
            local oam = {}
            for i = 0, 39 do
                oam[i+1] = emu:read8(0xFE00 + i)
            end
            results[#results+1] = {
                frame = f, lcdc = lcdc, bgp = bgp, obp0 = obp0, obp1 = obp1,
                obj_cram = obj, oam = oam,
            }
        end
    end
    if f >= SAMPLES[#SAMPLES] + 30 then
        local fh = io.open(OUT, "w")
        fh:write("[\n")
        for i, r in ipairs(results) do
            local function arr(t)
                local s = {}
                for j, v in ipairs(t) do s[j] = string.format("%02X", v) end
                return table.concat(s, ",")
            end
            fh:write(string.format(
                '  {"frame":%d,"lcdc":%d,"bgp":%d,"obp0":%d,"obp1":%d,' ..
                '"obj_cram":"%s","oam":"%s"}%s\n',
                r.frame, r.lcdc, r.bgp, r.obp0, r.obp1,
                arr(r.obj_cram), arr(r.oam),
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
        except (PermissionError, FileNotFoundError): pass


def probe(rom_path, out_path):
    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False) as luaf:
        luaf.write(PROBE_LUA); lua_path = Path(luaf.name)
    try:
        env = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
               "HOME": os.environ.get("HOME", "/tmp"), "PROBE_OUT": str(out_path),
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
    data = {}
    for rom in [Path("rom/working/penta_dragon_dx_v301.gb"),
                Path("rom/working/penta_dragon_dx_v301_attrinit.gb")]:
        out_json = out_dir / f"{rom.stem}_obj_palettes.json"
        print(f"=== {rom} ===")
        data[rom.name] = probe(rom, out_json)
    # Compare
    for f_idx in range(4):
        prod = data["penta_dragon_dx_v301.gb"][f_idx]
        aii = data["penta_dragon_dx_v301_attrinit.gb"][f_idx]
        print(f"\n=== f={prod['frame']} ===")
        for k in ["lcdc", "bgp", "obp0", "obp1"]:
            same = prod[k] == aii[k]
            print(f"  {k:>6} prod=0x{prod[k]:02X} aii=0x{aii[k]:02X} {'OK' if same else 'DIFF !!'}")
        same_obj = prod["obj_cram"] == aii["obj_cram"]
        print(f"  obj_cram (first 32B): {'SAME' if same_obj else 'DIFFERENT'}")
        if not same_obj:
            print(f"    prod: {prod['obj_cram']}")
            print(f"    aii:  {aii['obj_cram']}")
        same_oam = prod["oam"] == aii["oam"]
        print(f"  oam (first 10 sprites): {'SAME' if same_oam else 'DIFFERENT'}")
        if not same_oam:
            print(f"    prod: {prod['oam']}")
            print(f"    aii:  {aii['oam']}")


if __name__ == "__main__":
    main()
