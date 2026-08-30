#!/usr/bin/env python3
"""Audio contract: secret/clear melodies cannot be cut off by incidental SFX."""

from pathlib import Path

from test_dungeon_tools import ENTITIES, PLAYER, boot, clear_entities, use_tool


ROOT = Path(__file__).resolve().parent.parent


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def structural_contract():
    core = (ROOT / "src/audio/sfx.c").read_text()
    header = (ROOT / "src/audio/sfx.h").read_text()
    rewards = (ROOT / "src/audio/reward_sfx.c").read_text()
    weapons = (ROOT / "src/audio/weapon_sfx.c").read_text()

    assert "melody_lock(MELODY_PRIORITY_SECRET, 45)" in core
    assert "melody_lock(MELODY_PRIORITY_CLEAR, 18)" in core
    assert "priority < melody_lock_priority" in core
    rune = core.split("void sfx_play_rune", 1)[1].split("void sfx_tick", 1)[0]
    assert "if (melody_lock_frames) return;" not in rune, (
        "floor-note input was muted by an incidental room melody"
    )
    assert "u8 sfx_melody_locked(void)" in core
    assert "u8 sfx_melody_locked(void);" in header
    assert "kind != SFX_REWARD_SIGIL && sfx_melody_locked()" in rewards
    assert "melody_lock(MELODY_PRIORITY_MAJOR, 70)" in core
    assert "case SFX_SIGIL:" in core
    for frequency in (1547, 1750, 1798, 1849, 1881, 1922):
        assert str(frequency) in core, (
            f"major Sigil fanfare lost authored note {frequency}"
        )
    assert weapons.count("if (sfx_melody_locked()) return;") == 2


def live_coin_collision():
    pb = boot()
    clear_entities(pb)
    # Echo Chime starts the same long discovery figure used by pushed blocks,
    # hidden walls, and dungeon-law switches.
    use_tool(pb, 1, 41)

    coins_before = pb.memory[PLAYER + 16] | (pb.memory[PLAYER + 17] << 8)
    pickup = ENTITIES
    pb.memory[pickup] = 3          # ENT_PICKUP
    pb.memory[pickup + 1] = 3      # EF_ACTIVE | EF_ALIVE
    put16(pb, pickup + 3, (pb.memory[PLAYER + 9]
          | (pb.memory[PLAYER + 10] << 8)) + 5)
    put16(pb, pickup + 7, (pb.memory[PLAYER + 11]
          | (pb.memory[PLAYER + 12] << 8)) + 9)
    pb.memory[pickup + 14] = 1
    pb.memory[pickup + 16] = 240
    pb.memory[pickup + 17] = 1     # PICKUP_COIN_1
    pb.memory[pickup + 25] = 0x66

    envelopes = []
    for _ in range(48):
        pb.tick()
        envelopes.append(pb.memory[0xFF12])  # CH1 envelope
    coins_after = pb.memory[PLAYER + 16] | (pb.memory[PLAYER + 17] << 8)
    assert coins_after == coins_before + 1, (
        "priority lock prevented the coincident pickup itself"
    )
    assert 0xD2 not in envelopes[:8], (
        f"coin chirp replaced the discovery voice: {envelopes[:8]}"
    )
    assert 0xB4 in envelopes and 0xD6 in envelopes, (
        f"scheduled Ab4/D5 discovery envelopes did not resolve: {envelopes}"
    )
    pb.stop(save=False)


def main():
    structural_contract()
    live_coin_collision()
    print("[sfx-priority] PASS live coin collected under intact secret figure; "
          "major Sigil fanfare + clear/core/reward/weapon/equip/rune locks")


if __name__ == "__main__":
    main()
