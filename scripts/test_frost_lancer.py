#!/usr/bin/env python3
"""ROM contract: Frost Vault's Lancer uses authored charge speed and art."""

from pathlib import Path

from test_enemy_identity import generated_sprite
from test_stage_archetypes import EN, TM, generated_room


ENTITY_SIZE = 28
ENT_ENEMY = 2
EF_ACTIVE = 0x01
ENEMY_FROST_LANCER = 28
SPR_FROST_LANCER = 79


def put_fix8(pb, address, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (i * 8)) & 0xFF


def active_lancer(pb):
    for i in range(32):
        ep = EN + i * ENTITY_SIZE
        if (pb.memory[ep] == ENT_ENEMY and pb.memory[ep + 1] & EF_ACTIVE
                and pb.memory[ep + 17] == ENEMY_FROST_LANCER):
            return ep
    return None


def main():
    seen = []

    def probe(pb, _tiles):
        lancer = active_lancer(pb)
        if lancer is None:
            return
        seen.append(1)

        actual = bytes(pb.memory[0x8000 + SPR_FROST_LANCER * 16:
                                 0x8000 + (SPR_FROST_LANCER + 1) * 16])
        expected = generated_sprite("sprite_enemy_frost_lancer")
        assert actual == expected, "Frost Vault did not install Frost Lancer OBJ art"
        assert actual != generated_sprite("sprite_enemy_mirror_moth"), \
            "Frost Lancer reused Mirror Moth's silhouette"

        # Open the board and force a live eastward charge. The Lancer uses
        # the established two-pixel Charger cadence, but its long telegraph
        # and Frost-only spawn role make it a distinct readable lane prompt.
        for i in range(32):
            ep = EN + i * ENTITY_SIZE
            if ep != lancer:
                pb.memory[ep] = pb.memory[ep + 1] = 0
        for i in range(20 * 17):
            pb.memory[TM + i] = 1
        put_fix8(pb, lancer + 2, 64)
        put_fix8(pb, lancer + 6, 64)
        pb.memory[lancer + 19] = 2  # CHG_CHARGE
        pb.memory[lancer + 20] = 8  # charge duration
        pb.memory[lancer + 21] = 2  # east dir8
        pb.tick()
        assert pb.memory[lancer + 3] == 66, (
            f"Frost Lancer lost its established two-pixel charge: x={pb.memory[lancer + 3]}")

    table = (Path(__file__).resolve().parent.parent / "src/generated/enemies.c").read_text()
    assert '.id=28, .name="Frost Lancer", .sprite_set=79, .palette=6,' in table
    assert '.ai_kind=AI_CHARGER, .ai_p0=34, .ai_p1=96,' in table, \
        "Frost Lancer lost its authored tell/charge"

    for seed in range(0xF2057000, 0xF2057020):
        generated_room(3, seed, probe=probe)
        if seen:
            break
    assert seen, "Frost Lancer did not appear in 32 fixed Frost Vault procgen seeds"
    print("[frost-lancer] PASS Frost procgen spawn + unique art + readable charge")


if __name__ == "__main__":
    main()
