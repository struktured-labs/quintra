#!/usr/bin/env python3
"""Classify save states by their OAM-machinery liveness.

Tests run against save states whose initial state (DF1F, IME, wrapper-stall)
can differ from "normal gameplay". A save where the wrapper / OAM DMA /
hwoam_recolor are all dead produces TEST FAILURES that look like
"colorize-chain broken" but are actually "the save state never executes
forward".

This script writes a known-different poison value (0xAB) to 0xFE03 (Sara
slot 0 attr byte) at frame 1, runs forward for 30 frames, and reads back.
If the value is restored to something else (typically the colorize chain's
expected pal, with `AND F8 ; OR pal` semantics), the OAM machinery is
LIVE. If the 0xAB persists unchanged, the OAM is FROZEN — wrapper,
DMA, hwoam_recolor are all silent.

Run:

    uv run python scripts/diagnostics/classify_savestates.py [save ...]

Or with no arguments to scan all save states in `save_states_for_claude/`.

Findings (iter 26, 2026-06-18 against teleport.gb):

  | Save                                            | DF1F | Status |
  |-------------------------------------------------|------|--------|
  | level1_sara_w_alone.ss0                          | 0xFE | LIVE   |
  | level1_sara_w_mage_health1_items.ss0             | 0xFE | LIVE   |
  | level1_sara_w_metal_ball_mage_soldier.ss0        | 0xFE | LIVE   |
  | level1_sara_w_orc_healpotion1_poison_cure.ss0    | 0xFE | LIVE   |
  | level1_sara_w_spier_miniboss.ss0                 | 0xFF | FROZEN |
  | level1_sara_w_4_hornets.ss0                      | 0xFF | FROZEN |

Hard correlation: DF1F=0xFF saves are FROZEN; DF1F=0xFE saves are LIVE.

Implication for `tests/color_regression_tests.yaml`: the
`spider_miniboss_sara_w/sara_d` and `hornets` tests run against FROZEN
saves. Whatever palettes they observe are the captured OAM state, not
the live colorize chain's output. Failures in those tests are
test-data artifacts, not regressions in our color chain. Tests against
LIVE saves (mage, orc, metal_ball) DO probe the colorize chain;
failures there reflect real test-vs-implementation expectation gaps
(e.g., colorizer dispatch for tile 0x10-0x1F → pal 4 ORANGE clashes
with the YAML assertion `Sara slot expectations: pal 2`).

This file is the breadcrumb for someone updating the regression suite
to either (a) replace frozen savestates with re-captured live ones, or
(b) mark frozen-save tests as such and document expected static OAM.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROM = "rom/working/penta_dragon_dx_teleport.gb"
SAVE_DIR = Path("save_states_for_claude")

LUA_SCRIPT = '''
local LOG = io.open("%(log)s", "w")
local function log(m) if LOG then LOG:write(m.."\\n"); LOG:flush() end end
local f = 0
callbacks:add("frame", function()
  f = f + 1
  if f == 1 then
    log(string.format("DF1F=0x%%02X DCBB=0x%%02X D880=0x%%02X FFBE=%%d FFBF=%%d",
      emu:read8(0xDF1F), emu:read8(0xDCBB), emu:read8(0xD880),
      emu:read8(0xFFBE), emu:read8(0xFFBF)))
    emu:write8(0xFE03, 0xAB)
  end
  if f == 30 then
    local v = emu:read8(0xFE03)
    log(string.format("RESULT: FE03=0x%%02X %%s",
      v, v == 0xAB and "FROZEN" or "LIVE"))
    emu:stop()
  end
end)
'''


def classify_save(save_path: Path) -> dict:
    log_path = Path(tempfile.gettempdir()) / f"classify_{save_path.stem}.log"
    script_path = Path(tempfile.gettempdir()) / f"classify_{save_path.stem}.lua"
    script_path.write_text(LUA_SCRIPT % {"log": str(log_path)})

    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["SDL_AUDIODRIVER"] = "dummy"
    cmd = [
        "timeout", "15", "xvfb-run", "-a",
        "mgba-qt", ROM, "-t", str(save_path),
        "--script", str(script_path), "-l", "0",
    ]
    try:
        subprocess.run(cmd, env=env, capture_output=True, timeout=20)
    except subprocess.TimeoutExpired:
        return {"save": save_path.name, "status": "TIMEOUT"}

    if not log_path.exists():
        return {"save": save_path.name, "status": "NO_LOG"}

    lines = log_path.read_text().strip().splitlines()
    state = lines[0] if lines else ""
    result = lines[1] if len(lines) > 1 else "NO_RESULT"
    status = "FROZEN" if "FROZEN" in result else ("LIVE" if "LIVE" in result else "UNKNOWN")
    return {"save": save_path.name, "state": state, "result": result, "status": status}


def main() -> int:
    if not Path(ROM).exists():
        print(f"ROM not found: {ROM}")
        return 1
    if shutil.which("mgba-qt") is None or shutil.which("xvfb-run") is None:
        print("mgba-qt and xvfb-run are required on PATH.")
        return 1

    if len(sys.argv) > 1:
        saves = [Path(p) for p in sys.argv[1:]]
    else:
        saves = sorted(SAVE_DIR.glob("level1_*.ss0"))

    print(f"Classifying {len(saves)} save state(s)")
    print(f"{'STATUS':<10} {'SAVE':<60} {'STATE'}")
    print("-" * 120)

    results = []
    for s in saves:
        r = classify_save(s)
        results.append(r)
        print(f"{r['status']:<10} {r['save']:<60} {r.get('state', '')}")

    n_live = sum(1 for r in results if r["status"] == "LIVE")
    n_frozen = sum(1 for r in results if r["status"] == "FROZEN")
    n_other = len(results) - n_live - n_frozen
    print("-" * 120)
    print(f"SUMMARY: {n_live} LIVE, {n_frozen} FROZEN, {n_other} other")
    return 0


if __name__ == "__main__":
    sys.exit(main())
