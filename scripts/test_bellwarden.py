#!/usr/bin/env python3
"""Live-ROM contract for the guaranteed late Bellwarden miniboss encounter."""
import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import STAGE_START, dungeon_size, mission_graph
from test_stage_archetypes import generated_room

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


RS, PL, EN, TM, SCREEN = map(addr, (
    "_run_state", "_player", "_entities", "_room_tilemap",
    "_loop_current_screen",
))
SCREEN_ROOM, SCREEN_DIALOG = 5, 10


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def boot_to_miniboss(stage, role="warden"):
    """Generate one real authored miniboss in its seeded mission cell.

    Since #78 the Riftwild gate lands on the seeded foyer instead of
    incrementing the room counter, so it can no longer be aimed at an
    arbitrary role cell. Enter the stage through the live gate, then cross
    the real maze edge into the role cell (shared archetype harness).
    """
    local = mission_graph(dungeon_size(stage), 0xCAFE1234, stage)[role]
    pb = generated_room(stage, 0xCAFE1234, local_room=local,
                        keep_running=True)
    assert pb.memory[RS + 1] == STAGE_START[stage] + local, (
        f"could not generate stage {stage} miniboss; "
        f"got room={pb.memory[RS + 1]}")
    assert pb.memory[SCREEN] == SCREEN_ROOM, "miniboss room is not live"
    pb.tick(60)
    return pb


def enemies(pb):
    return [EN + i * ENTITY_SIZE for i in range(32)
            if pb.memory[EN + i * ENTITY_SIZE] == ENT_ENEMY
            and pb.memory[EN + i * ENTITY_SIZE + 1] & 1]


def kill_bellwarden_for_reward(pb, bell):
    """Deliver a real lethal player shot; only the tagged Bell may pay a weapon.

    The generated court is a scrolling arena, so line the Bell up beside the
    champion and fire the real B weapon rather than poking a synthetic
    projectile into a reused entity slot.
    """
    def g16(address):
        return pb.memory[address] | (pb.memory[address + 1] << 8)

    pb.memory[bell + 14] = 1
    for _ in range(8):
        if pb.memory[bell] != ENT_ENEMY or not pb.memory[bell + 1] & 1:
            break
        pb.memory[PL + 15] = 120
        # Face into the court, away from the edge door just walked through.
        side = "left" if g16(PL + 9) >= 96 else "right"
        put16(pb, bell + 3, g16(PL + 9) + (-32 if side == "left" else 32))
        put16(pb, bell + 7, g16(PL + 11))
        pb.button(side)
        pb.tick(2)
        pb.button("b")
        pb.tick(10)
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
            assert pb.memory[RS + 27] & (1 << 3), \
                "first Bellwarden kill did not persist its Warden Boon"
        pb.stop(save=False)

    deep = boot_to_miniboss(6, role="deep_warden")
    deep_bell = next(
        e for e in enemies(deep)
        if deep.memory[e + 17] == ENEMY_DREAD_BELL
    )
    kill_bellwarden_for_reward(deep, deep_bell)
    assert deep.memory[RS + 28] & (1 << 7), \
        "generated deep Bellwarden kill did not persist the deep-Warden seal"
    deep.stop(save=False)

    print("[bellwarden] PASS Sentinel early; tagged Bell + Warden stages 6-8; "
          "weapon reward + deep-Warden seal")


if __name__ == "__main__":
    main()
