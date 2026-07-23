#!/usr/bin/env python3
"""ROM regression: nine stage tracks and nine dedicated boss tracks."""
import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import (
    STAGE_BOSS_ROOM, STAGE_START, dungeon_direction, dungeon_size,
)

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
ROOM_W = 20


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


RS, PL, EN, TM, MUSIC, REQUEST = map(
    addr, ("_run_state", "_player", "_entities", "_room_tilemap",
           "_music_track_id", "_music_stage_number")
)
MUSIC_ROW = addr("_music_row")


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def boot_run():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    assert pb.memory[MUSIC] == 18, "title did not select music number 18"
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(60):
        pb.tick()
    return pb


def runtime_track(stage, boss):
    pb = boot_run()
    desired_room = STAGE_BOSS_ROOM[stage] if boss else (
        1 if stage == 0 else STAGE_START[stage])
    pb.memory[RS + 1] = desired_room - 1
    pb.memory[RS + 11] = stage       # bosses_beaten drives stage identity
    pb.memory[RS + 12] = 0
    pb.memory[RS + 13] = 0
    # Boss-route injection starts at the sanctuary.  Mirror a legitimate
    # completed room-2 objective so the persistent Rift Sigil gate admits
    # the synthetic traversal instead of making music coverage bypass it.
    if boss:
        sigils = pb.memory[RS + 23] | (pb.memory[RS + 24] << 8)
        sigils |= (1 << stage)
        pb.memory[RS + 23] = sigils & 0xFF
        pb.memory[RS + 24] = sigils >> 8
        pb.memory[RS + 27] = 1 << 3
        if dungeon_size(stage) >= 12:
            pb.memory[RS + 27] |= 1 << 7
        if dungeon_size(stage) >= 14:
            pb.memory[RS + 28] |= 1 << 7
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == 2:
            pb.memory[ep] = pb.memory[ep + 1] = 0
    assert pb.memory[RS + 11] == stage, "stage identity write did not stick"
    if boss:
        pb.memory[RS + 6] = 0xFF      # no backtracking direction
        pb.memory[RS + 17] = 0
        source_local = desired_room - 1 - STAGE_START[stage]
        target_local = desired_room - STAGE_START[stage]
        direction = dungeon_direction(source_local, target_local)
        for tx, ty in {
            0: ((9, 0), (10, 0)), 1: ((19, 8), (19, 9)),
            2: ((9, 16), (10, 16)), 3: ((0, 8), (0, 9)),
        }[direction]:
            pb.memory[TM + ty * ROOM_W + tx] = 3
        x, y = {
            0: (72, 0), 1: (144, 60),
            2: (72, 120), 3: (0, 60),
        }[direction]
        put16(pb, PL + 9, x)
        put16(pb, PL + 11, y)
    else:
        pb.memory[RS + 17] = 1        # Riftwild dungeon gate
        pb.memory[RS + 18] = 6
        put16(pb, PL + 9, 72)
        put16(pb, PL + 11, 60)
        pb.memory[TM + 9 * ROOM_W + 10] = 1
        pb.tick()                      # settle synthetic state
        pb.memory[TM + 9 * ROOM_W + 10] = 34  # BGT_PORTAL under feet
    for _ in range(30):
        pb.tick()
        if pb.memory[RS + 1] == desired_room:
            break
    assert pb.memory[RS + 1] == desired_room, (
        f"could not enter stage {stage} {'boss' if boss else 'room'}"
    )
    assert pb.memory[RS + 11] == stage, "transition changed stage identity"
    assert pb.memory[RS + 17] == 0, "transition did not enter a dungeon"
    track = pb.memory[MUSIC]
    assert pb.memory[REQUEST] == stage, (
        f"audio request drifted for stage {stage}: {pb.memory[REQUEST]}"
    )
    pb.stop(save=False)
    return track


def stage_door_keeps_phrase():
    """A real same-stage doorway must not restart the sequencer at row zero."""
    pb = boot_run()
    for i in range(32):
        ep = EN + i * 28
        pb.memory[ep] = pb.memory[ep + 1] = 0
    # Start well away from the loop boundary. The slide takes enough frames
    # for the row to advance a little, but a mistaken `music_play_stage()`
    # would reset it near zero instead of preserving this phrase position.
    pb.memory[MUSIC_ROW] = 17
    pb.memory[TM + 9 * ROOM_W + 19] = 3  # east BGT_DOOR
    put16(pb, PL + 9, 144)
    put16(pb, PL + 11, 60)
    for _ in range(80):
        pb.tick()
        if pb.memory[RS + 1] == 1:
            break
    assert pb.memory[RS + 1] == 1, "real east door did not enter room 1"
    assert pb.memory[MUSIC] == 0, "same-stage door changed exploration track"
    # 17 remains safely distinct from a reset row (0..2) across the short
    # streamed transition. This also detects an accidental stop/restart.
    assert pb.memory[MUSIC_ROW] >= 17, (
        f"stage phrase restarted across door: row={pb.memory[MUSIC_ROW]}"
    )
    pb.stop(save=False)


def table_pairs(name):
    """Return (melody, bass) source pairs from the compiled-in lookup table.

    GBC audio-register reads are not observable in every PyBoy backend.  The
    ROM traversal above proves each route enters its runtime track; this small
    source contract prevents an otherwise invisible regression where those
    routes use distinct IDs but point back to the same authored phrase.
    """
    text = (ROOT / "src/audio/music.c").read_text()
    match = re.search(
        rf"static const music_variant_t {name}\[MUSIC_STAGE_COUNT\] = \{{(.*?)\n\}};",
        text,
        re.S,
    )
    assert match, f"missing {name} table"
    pairs = re.findall(r"\{\s*(\w+),\s*(\w+),\s*\d+\s*\}", match.group(1))
    assert len(pairs) == 9, f"{name} table changed shape: {pairs}"
    return pairs


def main():
    stages = [runtime_track(stage, False) for stage in range(9)]
    bosses = [runtime_track(stage, True) for stage in range(9)]
    stage_phrases = table_pairs("stage_music")
    boss_phrases = table_pairs("boss_music")
    assert stages == list(range(9)), f"stage music numbers drifted: {stages}"
    assert bosses == list(range(9, 18)), f"boss music numbers drifted: {bosses}"
    assert set(stages).isdisjoint(bosses), "boss music reused an exploration id"
    assert len(set(stage_phrases)) == 9, f"stage phrases overlap: {stage_phrases}"
    assert len(set(boss_phrases)) == 9, f"boss phrases overlap: {boss_phrases}"
    stage_door_keeps_phrase()
    print(f"[music] PASS stages={stages}, bosses={bosses}, distinct phrases=18, title=18")


if __name__ == "__main__":
    main()
