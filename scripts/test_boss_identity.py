#!/usr/bin/env python3
"""ROM regression: final boss art and behavior differ from the first boss."""
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
ROOM_W = 20
SPR_BOSS_BIG = 40


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


RS, PL, EN, TM = map(addr, ("_run_state", "_player", "_entities", "_room_tilemap"))


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def enter_boss(stage, keep_open=False):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(60):
        pb.tick()

    target = (stage + 1) * 6
    pb.memory[RS + 1] = target - 1
    pb.memory[RS + 11] = stage
    pb.memory[RS + 6] = 0xFF
    # The sanctuary before each boss correctly requires that stage's Rift
    # Sigil. This identity harness is sampling an already-qualified stage,
    # so grant that objective instead of mistaking its progression gate for
    # a failed room transition.
    put16(pb, RS + 23, 1 << stage)
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == 2:
            pb.memory[ep] = pb.memory[ep + 1] = 0
    pb.memory[TM + 9 * ROOM_W + 19] = 3
    put16(pb, PL + 9, 144)
    put16(pb, PL + 11, 60)
    for _ in range(50):
        pb.tick()
        if pb.memory[RS + 1] == target:
            break
    assert pb.memory[RS + 1] == target, f"could not enter boss stage {stage}"
    # room_counter advances at transition start; allow the banked generator
    # and fade-in to finish before inspecting entities and loaded OBJ tiles.
    for _ in range(60):
        pb.tick()

    boss = None
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == 2 and pb.memory[ep + 17] == 1:
            boss = ep
            break
    active = [
        (pb.memory[EN + i * 28], pb.memory[EN + i * 28 + 1],
         pb.memory[EN + i * 28 + 17], pb.memory[EN + i * 28 + 19])
        for i in range(32) if pb.memory[EN + i * 28 + 1] & 1
    ]
    assert boss is not None, f"stage {stage} did not spawn its large boss: {active}"
    assert pb.memory[boss + 12] == SPR_BOSS_BIG, "large boss tile slot drifted"
    assert pb.memory[boss + 20] & 1, "boss giant flag missing"
    assert pb.memory[boss + 19] == stage, "boss attack variant does not match stage"

    # CPU-visible VRAM reads are blocked during active LCD transfer. This
    # disposable test instance can disable the LCD after taking its screenshot
    # and then inspect the loaded OBJ bytes directly.
    shot = ROOT / "tmp" / f"boss-stage-{stage}.png"
    shot.parent.mkdir(exist_ok=True)
    pb.screen.image.save(shot)
    pb.memory[0xFF40] = pb.memory[0xFF40] & 0x7F
    pb.memory[0xFF4F] = 0  # OBJ tile bytes live in VRAM bank 0
    art = bytes(pb.memory[0x8000 + SPR_BOSS_BIG * 16:
                          0x8000 + (SPR_BOSS_BIG + 16) * 16])
    if keep_open:
        # Restore LCD before handing the live encounter to the phase test.
        pb.memory[0xFF40] = pb.memory[0xFF40] | 0x80
        return pb, boss
    pb.stop(save=False)
    return art


def main():
    art = [enter_boss(stage) for stage in range(9)]
    assert len(set(art)) == 9, "not all nine stage bosses load distinct VRAM art"
    colossus, void_lord = art[0], art[8]
    assert colossus != void_lord, (
        f"Void Lord VRAM art equals first Colossus "
        f"(nonzero={sum(b != 0 for b in colossus)}, first={colossus[:8].hex()})"
    )
    differing = sum(a != b for a, b in zip(colossus, void_lord))
    assert differing >= 8, f"Void Lord crown is not visually substantial ({differing} bytes)"
    pb, boss = enter_boss(0, keep_open=True)
    max_hp = pb.memory[boss + 23]  # ai_data[6], captured by boss_tick
    assert max_hp > 1, "boss never captured its starting HP for enrage"
    hostile_count = lambda: sum(
        pb.memory[EN + i * 28] == 1
        and pb.memory[EN + i * 28 + 1] & 1
        and not (pb.memory[EN + i * 28 + 1] & 0x10)
        for i in range(32)
    )
    before_rift_shots = hostile_count()
    pb.memory[boss + 14] = max_hp // 2
    for _ in range(2):
        pb.tick()
    assert pb.memory[boss + 20] & 0x80, "boss did not enter its half-health riftbreak"
    assert pb.memory[boss + 18] >= 20, "riftbreak did not grant a readable recovery beat"
    rift_shot_delta = hostile_count() - before_rift_shots
    assert rift_shot_delta >= 4, "riftbreak did not emit its slow four-way warning"
    pb.stop(save=False)
    print(f"[boss-id] PASS 9/9 distinct runtime silhouettes; "
          f"Colossus vs crowned Void Lord differs {differing}/256 bytes; "
          f"variants 0..8; riftbreak adds {rift_shot_delta} warning shots")


if __name__ == "__main__":
    main()
