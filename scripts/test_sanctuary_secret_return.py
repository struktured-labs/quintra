#!/usr/bin/env python3
"""A sanctuary-side cache always returns, even before boss qualification."""
import re
from pathlib import Path

from make_stage_states import (
    advance_to_sanctuary, boot_to_stage, select_rom_topology,
    symbol_addresses,
)


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom" / "working" / "quintra.gbc"
BGT_DOOR = 3
BGT_WALL_CRACK = 24
ROOM_W = 20


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def press_until(pb, button, frames, predicate):
    pb.button_press(button)
    try:
        for _ in range(frames):
            pb.tick()
            if predicate():
                return True
    finally:
        pb.button_release(button)
        pb.tick()
    return False


def main():
    select_rom_topology(ROM)
    addrs = symbol_addresses(ROM)
    rs, player, tilemap = (addrs[name] for name in (
        "_run_state", "_player", "_room_tilemap"))
    entities = addrs["_entities"]
    noi = ROM.with_suffix(".noi").read_text()
    match = re.search(r"DEF _room_secret_loot_timer 0x([0-9A-Fa-f]+)", noi)
    assert match, "missing secret-loot timer symbol"
    loot_timer = int(match.group(1), 16)
    # Stage 4 is the first dungeon after a village and deterministically puts
    # its sanctuary's obvious crack on the east wall for this fixture seed.
    pb, _ram, _ = boot_to_stage(ROM, addrs, 3, "easy", 3)  # Picsean
    sanctuary = advance_to_sanctuary(pb, addrs, 3)
    cracks = [(x, y) for y in range(17) for x in range(ROOM_W)
              if pb.memory[tilemap + y * ROOM_W + x] == BGT_WALL_CRACK]
    assert cracks, "Stage 4 sanctuary no longer exercises its side cache"
    x, y = cracks[0]
    assert x == ROOM_W - 1 and y not in (8, 9), cracks

    # Shoot the actual wall, then cross its actual off-center threshold.
    put16(pb, player + 9, 132)
    put16(pb, player + 11, y * 8 - 4)
    pb.memory[player + 13] = 1  # FACE_E
    pb.memory[player + 23] = 0  # fire cooldown
    pb.button_press("a"); pb.tick(); pb.button_release("a")
    for _ in range(30):
        pb.tick()
    assert pb.memory[tilemap + y * ROOM_W + x] == BGT_DOOR
    put16(pb, player + 9, 136)
    put16(pb, player + 11, y * 8 - 8)
    assert press_until(pb, "right", 120, lambda: pb.memory[rs + 13] == 2), \
        "sanctuary crack did not enter the cache overlay"

    # procgen publishes secret_pending=2 near the start of the banked room
    # build. Wait for room_enter to finish spawning and marking the hoard.
    for _ in range(600):
        timer = pb.memory[loot_timer] | pb.memory[loot_timer + 1] << 8
        if timer:
            break
        pb.tick()

    # Every hoard piece shares one visible 12-second clock. Marking lives on
    # ai_data[7], while the old per-pickup u8 lifespan is disabled.
    timer = pb.memory[loot_timer] | pb.memory[loot_timer + 1] << 8
    marked = []
    for i in range(32):
        ep = entities + i * 28
        if (pb.memory[ep] == 3 and pb.memory[ep + 1] & 1
                and pb.memory[ep + 24] & 0x80):
            marked.append(ep)
            assert pb.memory[ep + 16] == 0, \
                "secret loot retained its invisible individual expiry"
    assert 600 < timer <= 720 and len(marked) >= 8, (
        f"cache did not arm one 12-second hoard clock: timer={timer} "
        f"marked={len(marked)} screen={pb.memory[addrs['_loop_current_screen']]} "
        f"secret={pb.memory[rs + 13]} entities="
        f"{[(pb.memory[entities + i * 28], pb.memory[entities + i * 28 + 1], pb.memory[entities + i * 28 + 17], pb.memory[entities + i * 28 + 24]) for i in range(16)]}"
    )
    # A one-second boundary must play the quiet metallic tick on noise CH4.
    # The secret-found melody owns audio briefly, so sample the next complete
    # clock boundary after its lock has retired.
    while timer % 60 != 1 or timer > 660:
        pb.tick()
        timer = pb.memory[loot_timer] | pb.memory[loot_timer + 1] << 8
    pb.memory[0xFF22] = 0
    pb.tick()
    assert pb.memory[0xFF22] == 0x24 and pb.memory[0xFF21] == 0x51, \
        "secret-vault second boundary lacks its quiet tick"

    # Recreate the reported risk: the optional room was found before the
    # stage mission qualified the adjacent boss threshold.
    pb.memory[rs + 23] = pb.memory[rs + 24] = 0  # stage Sigils
    pb.memory[rs + 27] = 0                       # dungeon objectives
    pb.memory[rs + 28] = 0                       # deep switch/Warden

    # The west cache return shares the sanctuary's boss direction. It must
    # bypass that one progression check and restore the parent graph cell.
    put16(pb, player + 9, 0)
    put16(pb, player + 11, 60)
    returned = press_until(
        pb, "left", 180,
        lambda: pb.memory[rs + 13] == 0 and pb.memory[rs + 1] == sanctuary,
    )
    assert returned, (
        "cache return was mistaken for the locked boss entrance: "
        f"room={pb.memory[rs + 1]} secret={pb.memory[rs + 13]}"
    )
    pb.stop(save=False)
    print("[sanctuary-secret] PASS unqualified boss gate cannot trap cache return")


if __name__ == "__main__":
    main()
