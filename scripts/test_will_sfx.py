#!/usr/bin/env python3
"""A full Will meter plays SFX_WILL, never the victory theme or SFX_PUZZLE."""

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
    assert "NR2" not in voice, "Will chime rewrote the music lead"
    assert "ch4(" not in voice, "Will chime took the noise channel"
    assert "melody_lock(" not in voice, "Will chime locked out combat SFX"
    assert "ch1(0x00, 0x80, 0x82, 1923);" in voice
    assert "sfx_claim_channels(20, 0);" in voice
    assert "ch1_busy_frames > 2" in sfx
    assert "will_chime_pending = 1" in sfx

    arrival = sfx.split("case PEND_WILL_NOTE2:", 1)[1].split("break;", 1)[0]
    assert "0x91" in arrival and "1949" in arrival
    assert "NR2" not in arrival


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


def watch_bank(pb, on_ids, level, charge, owned):
    arm(pb, level, charge, owned)
    on_ids.clear()
    envelopes = []
    lows = []
    for _ in range(20):
        pb.memory[PLAYER + 15] = 200
        pb.memory[PLAYER + 2] = 20
        pb.tick()
        envelopes.append(pb.memory[0xFF12])
        lows.append(pb.memory[0xFF13])
    return envelopes, lows


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
        envelopes, _lows = watch_bank(pb, seen, 0, 89, 7)
        assert pb.memory[PLAYER + LEVEL_OFFSET] == 1, "intermediate tier did not bank"
        assert coin_id in seen, ("intermediate Will bank missed SFX_COIN", seen)
        assert will_id not in seen, ("intermediate bank played the full-meter chime", seen)
        assert puzzle_id not in seen, ("intermediate bank played the discovery jingle", seen)
        assert pb.memory[music] == before, "Will bank changed the music track"
        assert pb.memory[music] != MUSIC_VICTORY

        # Cap 4, tier 3 -> 4 is the full meter.
        envelopes, _lows = watch_bank(pb, seen, 3, 179, 7)
        assert pb.memory[PLAYER + LEVEL_OFFSET] == 4, "Will cap did not fill"
        assert pb.memory[PLAYER + WILL_OFFSET] == 90, "full meter did not hold a full bar"
        assert will_id in seen, ("full Will did not trigger SFX_WILL", seen)
        assert puzzle_id not in seen, ("full Will played SFX_PUZZLE", seen)
        assert coin_id not in seen, ("full Will played SFX_COIN", seen)
        assert pb.memory[music] == before, "full Will started a new music track"
        assert pb.memory[music] != MUSIC_VICTORY, "full Will played the victory theme"
        # NR13/NR14 are write-only, so the live pitch check is the envelope
        # pair this voice alone schedules: quiet C6, then the short E6 arrival.
        assert 0x82 in envelopes and 0x91 in envelopes, (
            "quiet C6->E6 envelopes missing", envelopes)
        assert envelopes.index(0x82) < envelopes.index(0x91), (
            "E6 arrival preceded the C6 attack", envelopes)
        assert 0xA4 not in envelopes and 0xD6 not in envelopes, (
            "discovery-fanfare envelopes leaked into the Will chime", envelopes)
    finally:
        pb.stop(save=False)
    print("[will-sfx] PASS full meter plays SFX_WILL; victories and secrets keep their cues")


if __name__ == "__main__":
    main()
