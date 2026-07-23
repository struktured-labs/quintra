#!/usr/bin/env python3
"""Live-ROM contract: Ember exposes both early movement timing lessons."""

from test_stage_archetypes import EN, generated_room


ENTITY_SIZE = 28
ENT_ENEMY, EF_ACTIVE = 2, 0x01
ENEMY_FOLD_STAR, ENEMY_RIFT_OOZE = 11, 15


def active_enemy_ids(pb):
    return {
        pb.memory[EN + i * ENTITY_SIZE + 17]
        for i in range(32)
        if (pb.memory[EN + i * ENTITY_SIZE] == ENT_ENEMY
            and pb.memory[EN + i * ENTITY_SIZE + 1] & EF_ACTIVE)
    }


def main():
    seen = set()

    def probe(pb, _tiles):
        seen.update(active_enemy_ids(pb) & {ENEMY_FOLD_STAR, ENEMY_RIFT_OOZE})

    # These are genuine generated combat rooms, not injected fixtures. A
    # bounded seed band keeps the assertion fast while proving the stage's
    # replacement roster can surface both the contracted-core and split/reform
    # lessons before Frost Vault.
    for seed in range(0xE8BE0000, 0xE8BE0020):
        # Ember local 2 is the paired phase-gate puzzle and correctly removes
        # hostiles. Sample ordinary graph cell 4 for this combat-roster proof.
        generated_room(2, seed, probe=probe, local_room=4)
        if seen == {ENEMY_FOLD_STAR, ENEMY_RIFT_OOZE}:
            break

    assert ENEMY_FOLD_STAR in seen, "Ember never generated its Fold Star timing lesson"
    assert ENEMY_RIFT_OOZE in seen, "Ember lost its Rift Ooze movement lesson"
    print("[ember-movement] PASS generated Fold Star + Rift Ooze before Frost")


if __name__ == "__main__":
    main()
