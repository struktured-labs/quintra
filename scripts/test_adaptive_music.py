#!/usr/bin/env python3
"""Live-ROM contract for phrase-latched room-reactive orchestration."""
import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import STAGE_BOSS_ROOM

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


PL, EN, RS = map(addr, ("_player", "_entities", "_run_state"))
HEALTH, HEALTH_T = map(addr, ("_music_health_tier", "_music_health_target"))
THREAT, THREAT_T = map(addr, ("_music_threat_tier", "_music_threat_target"))
CONTEXT, CONTEXT_T = map(addr, ("_music_context", "_music_context_target"))
POWER, POWER_T = map(addr, ("_music_power_tier", "_music_power_target"))
RELIC, RELIC_T = map(addr, ("_music_relic_tier", "_music_relic_target"))
PATTERN = addr("_music_pattern_row")
TRACK = addr("_music_track_id")


def put16(pb, where, value):
    pb.memory[where] = value & 0xFF
    pb.memory[where + 1] = (value >> 8) & 0xFF


def boot():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    pb.tick(240)
    pb.button("start")
    pb.tick(30)
    pb.button("a")
    pb.tick(90)
    return pb


def clear_entities(pb):
    for slot in range(32):
        base = EN + slot * 28
        pb.memory[base] = pb.memory[base + 1] = 0


def entity(pb, slot, kind, x, y, content=0, flags=0x07):
    base = EN + slot * 28
    for offset in range(28):
        pb.memory[base + offset] = 0
    pb.memory[base] = kind
    pb.memory[base + 1] = flags
    put16(pb, base + 3, x)
    put16(pb, base + 7, y)
    pb.memory[base + 14] = 40
    pb.memory[base + 17] = content
    pb.memory[base + 25] = 0x88
    return base


def settle_director(pb, frames=20):
    for _ in range(frames):
        # Keep synthetic enemies from turning this music test into combat.
        pb.memory[PL + 15] = 120
        pb.tick()


def force_phrase_latch(pb):
    pb.memory[PATTERN] = 0
    settle_director(pb, 14)


def main():
    pb = boot()
    try:
        clear_entities(pb)
        px = pb.memory[PL + 9] | pb.memory[PL + 10] << 8
        py = pb.memory[PL + 11] | pb.memory[PL + 12] << 8
        hp_max = max(8, pb.memory[PL + 1])
        pb.memory[PL + 1] = hp_max
        pb.memory[PL + 2] = hp_max
        force_phrase_latch(pb)
        assert pb.memory[HEALTH] == pb.memory[HEALTH_T] == 0
        assert pb.memory[THREAT] == pb.memory[THREAT_T] == 0

        # Four health bands are real pending states, not a binary low-HP cue.
        for hp, tier in ((hp_max * 3 // 4, 1),
                         (hp_max // 2, 2),
                         (max(1, hp_max // 4), 3)):
            pb.memory[PL + 2] = hp
            force_phrase_latch(pb)
            assert pb.memory[HEALTH] == pb.memory[HEALTH_T] == tier, (
                hp, pb.memory[HEALTH], pb.memory[HEALTH_T])

        # Proximity and population independently raise the pressure stem.
        pb.memory[PL + 2] = hp_max
        for slot in range(6):
            entity(pb, slot, 2, px + 12 + slot * 3, py + 8, content=0)
        force_phrase_latch(pb)
        assert pb.memory[THREAT] == pb.memory[THREAT_T] == 3

        # A live Sentinel/elite owns the miniboss arrangement priority.
        pb.memory[EN + 17] = 1  # ENEMY_STONE_SENTINEL
        force_phrase_latch(pb)
        assert pb.memory[CONTEXT] == pb.memory[CONTEXT_T] == 3

        # Merchants are a gentler context once combat bodies are gone.
        clear_entities(pb)
        entity(pb, 0, 3, px + 24, py, content=8)  # PICKUP_MERCHANT
        force_phrase_latch(pb)
        assert pb.memory[CONTEXT] == pb.memory[CONTEXT_T] == 1

        clear_entities(pb)
        prior_room = pb.memory[RS + 1]
        pb.memory[RS + 1] = STAGE_BOSS_ROOM[0] - 1
        force_phrase_latch(pb)
        assert pb.memory[CONTEXT] == pb.memory[CONTEXT_T] == 2
        pb.memory[RS + 1] = prior_room

        # Stage treasures sing at two distances, then vanish from the layer.
        relic = entity(pb, 0, 3, px + 72, py, content=11)  # Rift Sigil
        force_phrase_latch(pb)
        assert pb.memory[RELIC] == pb.memory[RELIC_T] == 1
        put16(pb, relic + 3, px + 24)
        force_phrase_latch(pb)
        assert pb.memory[RELIC] == pb.memory[RELIC_T] == 2
        pb.memory[relic] = pb.memory[relic + 1] = 0
        force_phrase_latch(pb)
        assert pb.memory[RELIC] == pb.memory[RELIC_T] == 0

        # A build materially ahead of its stage gets its own confident voice.
        pb.memory[PL + 5] = pb.memory[PL + 6] = pb.memory[PL + 7] = 20
        force_phrase_latch(pb)
        assert pb.memory[POWER] == pb.memory[POWER_T] == 1

        # Director writes do not restart a song or twitch the current section.
        # They become audible together only when the next 16-row phrase opens.
        track = pb.memory[TRACK]
        pb.memory[HEALTH] = pb.memory[THREAT] = pb.memory[POWER] = 0
        pb.memory[RELIC] = 0
        pb.memory[CONTEXT] = 0
        pb.memory[PATTERN] = 5
        pb.memory[PL + 2] = 1
        for slot in range(5):
            entity(pb, slot, 2, px + 8 + slot * 2, py + 8, content=0)
        settle_director(pb)
        assert pb.memory[HEALTH] == 0 and pb.memory[THREAT] == 0, (
            "adaptive state changed before a phrase boundary")
        force_phrase_latch(pb)
        assert pb.memory[HEALTH] == pb.memory[HEALTH_T] == 3
        assert pb.memory[THREAT] == pb.memory[THREAT_T] == 3
        assert pb.memory[TRACK] == track, "adaptive layer restarted the score"
    finally:
        pb.stop(save=False)

    print("[adaptive-music] PASS 4 HP tiers + pressure + miniboss/merchant "
          "+ power + two-range relic resonance, all phrase-latched")


if __name__ == "__main__":
    main()
