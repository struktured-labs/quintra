#!/usr/bin/env python3
"""A full Will meter plays the rising power-up, never the coin or victory theme."""

import re
from pathlib import Path

from test_will_max import (
    PLAYER, LEVEL_OFFSET, WILL_OFFSET, addr, boot, clear_arena,
)


ROOT = Path(__file__).resolve().parent.parent
MUSIC_VICTORY = int(re.search(
    r"#define MUSIC_VICTORY\s+(\d+)",
    (ROOT / "src/audio/music.h").read_text(),
).group(1))


def sfx_ids():
    body = (ROOT / "src/audio/sfx.h").read_text().split("enum {", 1)[1]
    body = body.split("};", 1)[0]
    ids = {}
    number = 0
    for raw in body.splitlines():
        line = raw.split("//", 1)[0].strip().rstrip(",")
        if not line:
            continue
        if "=" in line:
            name, value = (part.strip() for part in line.split("=", 1))
            number = int(value, 0)
        else:
            name = line
        ids[name] = number
        number += 1
    return ids


def structural_contract():
    sfx = (ROOT / "src/audio/sfx.c").read_text()
    header = (ROOT / "src/audio/sfx.h").read_text()
    will = (ROOT / "src/game/will_support.c").read_text()
    victory = (ROOT / "src/game/victory.c").read_text()
    room = (ROOT / "src/game/room.c").read_text()
    puzzle = (ROOT / "src/game/puzzle.c").read_text()

    assert "SFX_WILL," in header
    assert "SFX_WILL : SFX_COIN" in will
    assert "SFX_PUZZLE" not in will
    assert "music_play_victory" not in will
    assert "music_play_victory();" in victory
    assert "music_play_victory();" in room
    assert "sfx_play(SFX_PUZZLE);" in puzzle

    voice = sfx.split("case SFX_WILL:", 1)[1].split("default:", 1)[0]
    assert "sfx_play_will();" in voice
    assert "NR2" not in voice, "Will power-up rewrote the music lead"
    assert "ch4(" not in voice, "Will power-up took the noise channel"
    assert "melody_lock(" not in voice, "Will power-up locked out combat SFX"
    assert "ch1_busy_frames > 2" in sfx
    assert "will_chime_pending = 1" in sfx
    assert "if (id != SFX_WILL) sfx_will_active = 0;" in sfx

    rewards = (ROOT / "src/audio/reward_sfx.c").read_text()
    figure = rewards.split("void sfx_play_will", 1)[1]
    # The shipped figure is the rising sweep. It must not reuse the coin's
    # B5->E6 pair, its loud decreasing envelope, or a combat-level peak.
    assert "static const u8 will_sweep[WILL_NOTES] = { 0x55, 0x00 };" in rewards
    assert "static const u8 will_env[WILL_NOTES] = { 0x4C, 0xA1 };" in rewards
    assert "static const u16 will_freq[WILL_NOTES] = { 1547, 1964 };" in rewards
    assert "sfx_claim_channels(WILL_CLAIM, 0);" in figure
    assert "#define WILL_CLAIM 34" in rewards
    assert "1915" not in figure and "0xD2" not in figure
    assert "NR2" not in figure and "NR4" not in figure


def release(pb):
    for button in ("a", "b", "start", "select", "up", "down", "left", "right"):
        pb.button_release(button)


def arm(pb, level, charge, owned):
    pb.memory[PLAYER + 1] = 20
    pb.memory[PLAYER + 2] = 20
    pb.memory[PLAYER + 15] = 200
    pb.memory[PLAYER + 20] = 0
    pb.memory[PLAYER + 44] = owned
    pb.memory[PLAYER + LEVEL_OFFSET] = level
    pb.memory[PLAYER + WILL_OFFSET] = charge
    pb.memory[addr("_will_charge_fraction")] = 39


def watch_bank(pb, on_ids, level, charge, owned, frames):
    arm(pb, level, charge, owned)
    on_ids.clear()
    envelopes = []
    sweeps = []
    for _ in range(frames):
        pb.memory[PLAYER + 15] = 200
        pb.memory[PLAYER + 2] = 20
        pb.tick()
        envelopes.append(pb.memory[0xFF12])
        sweeps.append(pb.memory[0xFF10] & 0x7F)
    return envelopes, sweeps


def main():
    structural_contract()
    ids = sfx_ids()
    will_id = ids["SFX_WILL"]
    coin_id = ids["SFX_COIN"]
    puzzle_id = ids["SFX_PUZZLE"]
    pb = boot(0)
    try:
        clear_arena(pb)
        release(pb)
        seen = []
        music = addr("_music_track_id")
        entry = addr("_sfx_play")

        def on_sfx(_ctx):
            seen.append(pb.register_file.A)

        pb.hook_register(entry >> 16, entry & 0xFFFF, on_sfx, None)
        before = pb.memory[music]

        # Cap 4, tier 0 -> 1 still has room above it: coin blip only.
        envelopes, _sweeps = watch_bank(pb, seen, 0, 89, 7, 16)
        assert pb.memory[PLAYER + LEVEL_OFFSET] == 1, "intermediate tier did not bank"
        assert coin_id in seen, ("intermediate Will bank missed SFX_COIN", seen)
        assert will_id not in seen, ("intermediate bank played the full-meter chime", seen)
        assert puzzle_id not in seen, ("intermediate bank played the discovery jingle", seen)
        assert pb.memory[music] == before, "Will bank changed the music track"
        assert pb.memory[music] != MUSIC_VICTORY

        # Cap 4, tier 3 -> 4 is the full meter.
        envelopes, sweeps = watch_bank(pb, seen, 3, 179, 7, 36)
        assert pb.memory[PLAYER + LEVEL_OFFSET] == 4, "Will cap did not fill"
        assert pb.memory[PLAYER + WILL_OFFSET] == 90, "full meter did not hold a full bar"
        assert will_id in seen, ("full Will did not trigger SFX_WILL", seen)
        assert puzzle_id not in seen, ("full Will played SFX_PUZZLE", seen)
        assert coin_id not in seen, ("full Will played SFX_COIN", seen)
        assert pb.memory[music] == before, "full Will started a new music track"
        assert pb.memory[music] != MUSIC_VICTORY, "full Will played the victory theme"
        assert 0xD2 not in envelopes, ("coin envelope leaked into the power-up", envelopes)
        assert 0x4C in envelopes and 0xA1 in envelopes, (
            "sweep swell and top ring missing", envelopes)
        assert envelopes.index(0x4C) < envelopes.index(0xA1), (
            "top ring preceded the rising sweep", envelopes)
        assert 0x55 in sweeps, ("rising sweep was not armed", sweeps)
        assert sweeps.index(0x55) < envelopes.index(0xA1), (
            "top ring started before the sweep")
    finally:
        pb.stop(save=False)
    print("[will-sfx] PASS full meter plays the rising power-up; coin and victory stay put")


if __name__ == "__main__":
    main()
