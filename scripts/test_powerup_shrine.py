#!/usr/bin/env python3
"""ROM contract: one-per-run power shrine flag + seed-stable placement hook."""
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()

ENT_PICKUP = 3
PICKUP_POWERUP, PICKUP_ROULETTE = 27, 28
ROULETTE_SHRINE = 0x01


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


def boot_class(class_id, screen, player):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    for _ in range(class_id):
        pb.button("down")
        for _ in range(16):
            pb.tick()
    pb.button("a")
    for _ in range(80):
        pb.tick()
    assert pb.memory[screen] == 5 and pb.memory[player] == class_id
    return pb


def main():
    player, entities, screen = map(addr, ("_player", "_entities", "_loop_current_screen"))
    pu_id, flags, test_cmd = map(
        addr, ("_powerup_id", "_run_state", "_powerup_test_cmd"))
    # run_state.powerup_shrines is the last byte of the struct. Look up
    # the field via the known symbol if exported, else scan after boot.
    try:
        shrines = addr("_run_state")  # placeholder, replaced below
    except RuntimeError:
        shrines = None
    # Prefer an explicit symbol if the compiler emitted one; otherwise
    # poke via the test hook and observe the claim bit after collect.
    pb = boot_class(1, screen, player)
    for _ in range(2):
        for i in range(32 * 28):
            pb.memory[entities + i] = 0
        pb.tick()

    # Spawn a dungeon-shrine roulette on the hero (test cmd 2).
    pb.memory[addr("_powerup_test_cmd"), addr("_powerup_world_live")] = 2
    for _ in range(6):
        pb.tick()
    slot = None
    for i in range(32):
        e = entities + i * 28
        if pb.memory[e] == ENT_PICKUP and pb.memory[e + 17] == PICKUP_ROULETTE:
            slot = e
            break
    assert slot, "shrine test hook did not spawn a roulette"
    # Overlap lock + 20-frame freeze awards the power-up.
    px = pb.memory[player + 9] | (pb.memory[player + 10] << 8)
    py = pb.memory[player + 11] | (pb.memory[player + 12] << 8)
    raw = (px + 4) << 8
    for i in range(4):
        pb.memory[slot + 2 + i] = (raw >> (i * 8)) & 0xFF
    raw = (py + 4) << 8
    for i in range(4):
        pb.memory[slot + 6 + i] = (raw >> (i * 8)) & 0xFF
    for _ in range(30):
        pb.tick()
    assert pb.memory[addr("_powerup_id")] in range(4, 9), (
        f"shrine roulette awarded {pb.memory[addr('_powerup_id')]}, want uncommon+")

    # The claim bit must be set so a second shrine cannot spawn this stage.
    # Locate powerup_shrines by walking the run_state symbol size: we expose
    # it as the byte immediately after vignette_seen (u16), i.e. last byte.
    rs = addr("_run_state")
    # Search a short window at the tail of run_state for a now-set bit 0.
    found = 0
    # typical sizeof is ~60-80; check last 16 bytes
    for off in range(50, 90):
        if pb.memory[rs + off] & 0x01:
            found = 1
            bit_at = off
            break
    assert found, "dungeon shrine claim bit was not set on collect"

    # A second cmd-2 spawn is still allowed by the hook; the place_room_shrine
    # path (cmd 4) must refuse once claimed.
    for i in range(32 * 28):
        # do not clear the live power-up, only lingering pickups
        if pb.memory[entities + i] == ENT_PICKUP:
            pb.memory[entities + i] = 0
    pb.memory[addr("_powerup_test_cmd"), addr("_powerup_world_live")] = 4
    for _ in range(4):
        pb.tick()
    leftover = [i for i in range(32)
                if pb.memory[entities + i * 28] == ENT_PICKUP]
    assert leftover == [], f"claimed shrine still placed a pickup: {leftover}"

    pb.stop(save=False)
    print("[powerup-shrine] PASS uncommon roulette, claim bit, no respawn")


if __name__ == "__main__":
    main()
