#!/usr/bin/env python3
"""ROM contract: Toxic Mire's Bog Toad is live procgen with its own art."""

from pathlib import Path

from test_enemy_identity import generated_sprite
from test_stage_archetypes import EN, generated_room


ENTITY_SIZE = 28
ENT_ENEMY = 2
EF_ACTIVE = 0x01
ENEMY_BOG_TOAD = 26
SPR_BOG_TOAD = 79


def active_toad(pb):
    for i in range(32):
        ep = EN + i * ENTITY_SIZE
        if (pb.memory[ep] == ENT_ENEMY and pb.memory[ep + 1] & EF_ACTIVE
                and pb.memory[ep + 17] == ENEMY_BOG_TOAD):
            return ep
    return None


def main():
    seen = []

    def probe(pb, _tiles):
        toad = active_toad(pb)
        if toad is None:
            return
        seen.append(1)
        actual = bytes(pb.memory[0x8000 + SPR_BOG_TOAD * 16:
                                 0x8000 + (SPR_BOG_TOAD + 1) * 16])
        expected = generated_sprite("sprite_enemy_bog_toad")
        assert actual == expected, "Toxic Mire did not install Bog Toad OBJ art"
        assert actual != generated_sprite("sprite_enemy_mire_spore"), \
            "Bog Toad reused the Mine silhouette"

    enemy_table = (Path(__file__).resolve().parent.parent / "src/generated/enemies.c").read_text()
    assert '.id=26, .name="Bog Toad", .sprite_set=79, .palette=7,' in enemy_table
    assert '.ai_kind=AI_CHARGER, .ai_p0=28, .ai_p1=120,' in enemy_table, \
        "Bog Toad lost its authored telegraph/pounce parameters"

    for seed in range(0xB06A0000, 0xB06A0020):
        generated_room(4, seed, probe=probe)
        if seen:
            break
    assert seen, "Bog Toad did not appear in 32 fixed Toxic Mire procgen seeds"
    print("[bog-toad] PASS Toxic Mire procgen spawn + unique pounce silhouette")


if __name__ == "__main__":
    main()
