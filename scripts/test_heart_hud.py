#!/usr/bin/env python3
"""Hearts fill when collected, and a refusal says why."""
import re
from pathlib import Path

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
WIN = 0x9C00
SCREEN_ROOM = 5
ENT_PICKUP = 3
PICKUP_HEART = 0
HUD_HEART_FULL = 4
HUD_HEART_HALF = 5
HUD_HEART_EMPTY = 6
# BGR555 heart red (31, 6, 8) and the low-HP white flash (31, 26, 24).
HEART_RED = (0xDF, 0x20)
HEART_WHITE = (0x5F, 0x63)
HPFULL = (92, 90, 78, 65, 81, 81)
HUNGER = (92, 65, 91, 85, 86, 76)
NOHEAL = (91, 89, 92, 86, 84, 81)


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


RS, PL, EN, SCREEN, STATUS = map(addr, (
    "_run_state", "_player", "_entities", "_loop_current_screen",
    "_player_status_kind",
))


def tick(pb, count):
    for _ in range(count):
        pb.tick()


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def boot():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    tick(pb, 240)
    pb.button("start")
    tick(pb, 30)
    pb.button("a")
    for _ in range(240):
        pb.tick()
        if pb.memory[SCREEN] == SCREEN_ROOM:
            for slot in range(32):
                entity = EN + slot * 28
                if pb.memory[entity] == 2:
                    pb.memory[entity] = pb.memory[entity + 1] = 0
            pb.memory[PL + 2] = 10
            pb.memory[PL + 15] = 180
    assert pb.memory[SCREEN] == SCREEN_ROOM
    return pb


def put32(pb, address, value):
    for i in range(4):
        pb.memory[address + i] = (value >> (8 * i)) & 0xFF


def heart_color(pb):
    """BG palette 7, color 3, as two little-endian bytes."""
    pair = []
    for offset in (6, 7):
        pb.memory[0xFF68] = 0x80 | (7 * 8 + offset)
        pair.append(pb.memory[0xFF69])
    return tuple(pair)


def hearts(pb):
    return tuple(pb.memory[0, WIN + i] for i in range(8))


def notice(pb):
    return tuple(pb.memory[0, WIN + 10 + i] for i in range(6))


def clear_entities(pb):
    for slot in range(32):
        entity = EN + slot * 28
        pb.memory[entity] = pb.memory[entity + 1] = 0


def spawn_heart(pb):
    ep = EN
    px = pb.memory[PL + 9] | (pb.memory[PL + 10] << 8)
    py = pb.memory[PL + 11] | (pb.memory[PL + 12] << 8)
    clear_entities(pb)
    for offset in range(28):
        pb.memory[ep + offset] = 0
    pb.memory[ep] = ENT_PICKUP
    pb.memory[ep + 1] = 0x03
    put32(pb, ep + 2, px << 8)
    put32(pb, ep + 6, py << 8)
    pb.memory[ep + 12] = 35
    pb.memory[ep + 14] = 1
    pb.memory[ep + 16] = 30
    pb.memory[ep + 17] = PICKUP_HEART
    pb.memory[ep + 25] = 0x66
    return ep


def main():
    pb = boot()
    try:
        # Missing one heart, no curse: the pickup fills a HUD heart.
        pb.memory[PL + 46] = pb.memory[PL + 47] = 0
        pb.memory[PL + 2] = pb.memory[PL + 1] - 2
        before = hearts(pb)
        missing = pb.memory[PL + 2]
        heart = spawn_heart(pb)
        pb.tick()
        assert pb.memory[PL + 2] == missing + 1, (
            f"short a heart but the pickup was refused hp={pb.memory[PL + 2]}")
        assert not (pb.memory[heart + 1] & 1), "acknowledged heart stayed active"
        after = hearts(pb)
        assert before != after, f"HUD hearts did not change: {before} -> {after}"
        assert HUD_HEART_HALF in after or HUD_HEART_FULL in after

        # One heart, white pulse, then a heal must restore red on that frame.
        pb.memory[PL + 2] = 2
        saw_white = False
        for _ in range(48):
            pb.memory[PL + 2] = 2
            pb.memory[PL + 15] = 180
            pb.memory[STATUS] = 0
            pb.tick()
            if heart_color(pb) == HEART_WHITE:
                saw_white = True
                break
        assert saw_white, f"low HP never flashed white: {heart_color(pb)}"
        shown = hearts(pb)
        pb.memory[PL + 2] = 2
        pb.memory[PL + 15] = 180
        pb.memory[STATUS] = 0
        pb.memory[PL + 46] = pb.memory[PL + 47] = 0
        heart = spawn_heart(pb)
        pb.tick()
        assert pb.memory[PL + 2] == 3, (
            f"heal during the pulse did not apply hp={pb.memory[PL + 2]} "
            f"flags={pb.memory[heart+1]:02x} kind={pb.memory[heart+17]}")
        assert hearts(pb) != shown, "pulse heal did not change heart tiles"
        assert heart_color(pb) == HEART_RED, (
            f"white pulse stuck after leaving one heart: {heart_color(pb)}")

        # Full gauge: stay put and say HPFULL.
        pb.memory[PL + 2] = pb.memory[PL + 1]
        heart = spawn_heart(pb)
        pb.tick()
        assert pb.memory[heart] == ENT_PICKUP, "full HP consumed the heart"
        assert pb.memory[PL + 2] == pb.memory[PL + 1]
        assert notice(pb) == HPFULL, f"full HP refusal was silent: {notice(pb)}"
        pb.memory[heart] = pb.memory[heart + 1] = 0
        tick(pb, 50)

        # Short a heart, but Hunger blocks it and says so.
        pb.memory[PL + 2] = pb.memory[PL + 1] - 1
        pb.memory[PL + 46] = 0x08
        pb.memory[PL + 47] = 3
        hp = pb.memory[PL + 2]
        heart = spawn_heart(pb)
        pb.tick()
        assert pb.memory[PL + 2] == hp, "Hunger allowed a heal"
        assert pb.memory[heart] == ENT_PICKUP, "Hunger consumed the heart"
        text = notice(pb)
        assert text in (HUNGER, NOHEAL), f"Hunger refusal had no reason: {text}"
    finally:
        pb.stop(save=False)
    print("[heart-hud] PASS fill, white-pulse clear, HPFULL, hunger reason")


if __name__ == "__main__":
    main()
