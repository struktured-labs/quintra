#!/usr/bin/env python3
"""Live-ROM contract for the guaranteed late Bellwarden miniboss encounter."""
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()

ROOM_W = 20
ENTITY_SIZE = 28
ENT_ENEMY = 2
ENT_PROJECTILE = 1
ENT_PICKUP = 3
ENEMY_STONE_SENTINEL = 1
ENEMY_DREAD_BELL = 20
ENEMY_RIFT_WARDEN = 21
SPR_DREAD_BELL = 125
ENEMY_AUX_BELLWARDEN = 0xB1
EF_ACTIVE_ALIVE = 0x03
EF_PLAYER_PROJ = 0x10
PICKUP_WEAPON = 5


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


RS, PL, EN, TM = map(addr, ("_run_state", "_player", "_entities", "_room_tilemap"))


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def boot_to_miniboss(stage):
    """Generate the real local-room-3 miniboss through the Riftwild gate."""
    pb = PyBoy(str(ROM), window="null", cgb=True)
    pb.tick(240)
    pb.button("start")
    pb.tick(30)
    pb.button("a")
    pb.tick(60)

    # The gate invokes the actual room generator and palette/sprite orchestration.
    # Target local room 3 directly so this encounter contract is independent of
    # the deliberately nonlinear player route to it.
    target = stage * 6 + 3
    pb.memory[RS + 1] = target - 1
    for i, byte in enumerate((0xCAFE1234).to_bytes(4, "little")):
        pb.memory[RS + 2 + i] = byte
    pb.memory[RS + 11] = stage
    pb.memory[RS + 12] = 0
    pb.memory[RS + 13] = 0
    pb.memory[RS + 17] = 1
    pb.memory[RS + 18] = 6  # ZELDA_CELL_DUNGEON_ENTRANCE
    for i in range(32):
        entity = EN + i * ENTITY_SIZE
        if pb.memory[entity] in (ENT_ENEMY, ENT_PROJECTILE):
            pb.memory[entity] = pb.memory[entity + 1] = 0
    pb.memory[TM + 9 * ROOM_W + 10] = 34  # BGT_PORTAL under feet center
    put16(pb, PL + 9, 72)
    put16(pb, PL + 11, 60)
    for _ in range(90):
        pb.tick()
        if pb.memory[RS + 1] == target:
            break
    assert pb.memory[RS + 1] == target, (
        f"could not generate stage {stage} miniboss; got room={pb.memory[RS + 1]} "
        f"world={pb.memory[RS + 17]} entered={pb.memory[RS + 6]}")
    # Generation owns the first room frame. Eight active frames are enough to
    # commit entities while retaining most of the deliberately short enemy
    # arrival telegraphs for inspection.
    pb.tick(8)
    return pb


def enemies(pb):
    return [EN + i * ENTITY_SIZE for i in range(32)
            if pb.memory[EN + i * ENTITY_SIZE] == ENT_ENEMY
            and pb.memory[EN + i * ENTITY_SIZE + 1] & 1]


def kill_bellwarden_for_reward(pb, bell):
    """Deliver a real lethal player shot; only the tagged Bell may pay a weapon."""
    shot = next(EN + i * ENTITY_SIZE for i in range(32)
                if not (pb.memory[EN + i * ENTITY_SIZE + 1] & 1))
    bell_x, bell_y = pb.memory[bell + 3], pb.memory[bell + 7]
    pb.memory[bell + 14] = 1
    pb.memory[shot] = ENT_PROJECTILE
    pb.memory[shot + 1] = EF_ACTIVE_ALIVE | EF_PLAYER_PROJ
    put16(pb, shot + 3, bell_x)
    put16(pb, shot + 7, bell_y)
    pb.memory[shot + 14] = 1
    pb.memory[shot + 16] = 90
    pb.memory[shot + 25] = 0x77
    pb.memory[shot + 26] = 1
    put16(pb, PL + 9, 144)
    put16(pb, PL + 11, 112)
    pb.tick(8)
    kinds = [pb.memory[EN + i * ENTITY_SIZE + 17] for i in range(32)
             if pb.memory[EN + i * ENTITY_SIZE] == ENT_PICKUP
             and pb.memory[EN + i * ENTITY_SIZE + 1] & 1]
    assert PICKUP_WEAPON in kinds, (
        f"Bellwarden paid ordinary Bell drops instead of a weapon orb: {kinds}")


def main():
    # Earlier stages retain their varied, large Sentinel miniboss identity.
    early = boot_to_miniboss(5)
    early_ids = [early.memory[e + 17] for e in enemies(early)]
    assert ENEMY_STONE_SENTINEL in early_ids, (
        f"stage-5 Sentinel miniboss disappeared: {early_ids}")
    early.stop(save=False)

    for stage in (6, 7, 8):
        pb = boot_to_miniboss(stage)
        combatants = enemies(pb)
        ids = [pb.memory[e + 17] for e in combatants]
        assert ids.count(ENEMY_DREAD_BELL) == 1, (
            f"stage {stage} lacks its guaranteed Bellwarden: {ids}")
        assert ids.count(ENEMY_RIFT_WARDEN) == 1, (
            f"stage {stage} lacks its Bellwarden escort: {ids}")
        assert ENEMY_STONE_SENTINEL not in ids, (
            f"stage {stage} kept a generic Sentinel instead: {ids}")

        bell = next(e for e in combatants if pb.memory[e + 17] == ENEMY_DREAD_BELL)
        warden = next(e for e in combatants if pb.memory[e + 17] == ENEMY_RIFT_WARDEN)
        expected_bell_hp = 39 + (stage - 6) * 4
        expected_bell_damage = 2
        assert pb.memory[bell + 12] == SPR_DREAD_BELL, "Bellwarden lost Dread Bell art"
        assert pb.memory[bell + 13] == 6, "Bellwarden is not stage-tinted"
        assert pb.memory[bell + 19] == ENEMY_AUX_BELLWARDEN, (
            "Bellwarden lost its explicit miniboss-reward identity")
        assert pb.memory[bell + 14] == expected_bell_hp, (
            f"stage {stage} Bellwarden HP={pb.memory[bell + 14]}, "
            f"expected {expected_bell_hp}; live bosses={pb.memory[RS + 11]}")
        assert pb.memory[bell + 26] == expected_bell_damage, (
            f"stage {stage} Bellwarden damage={pb.memory[bell + 26]}, "
            f"expected {expected_bell_damage}")
        # The preceding visible slide can consume the initial 42-frame
        # telegraph. It must nevertheless be in the Bell's real 108-frame
        # cadence rather than an uninitialized or generic walker state.
        assert 0 < pb.memory[bell + 18] <= 108, "Bellwarden lost bell cadence"
        assert pb.memory[warden + 14] == 16, (
            f"stage {stage} Warden HP drifted")
        assert 0 < pb.memory[warden + 18] <= 92, "Warden lost fan cadence"
        if stage == 6:
            kill_bellwarden_for_reward(pb, bell)
        pb.stop(save=False)

    print("[bellwarden] PASS Sentinel early; tagged Bell + Warden stages 6-8; weapon reward")


if __name__ == "__main__":
    main()
