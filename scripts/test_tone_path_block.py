#!/usr/bin/env python3
"""Live-ROM contracts for the hidden-path tone-block puzzle (PUZZLE_TONE_PATH)."""

import os
from pathlib import Path

import numpy as np

from quintra_topology import (
    STAGE_START, dungeon_size, mission_graph, puzzle_slot_kind,
    PUZZLE_TONE_PATH,
)
from make_stage_states import symbol_addresses
from test_stage_archetypes import generated_room
from test_puzzles import (
    addr, put16, active_hostiles, visible_hostiles, clear_hostiles,
    RS, PL, TM, KIND, LOCKED,
)

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
PREVIEW = Path(os.environ.get(
    "TONE_PATH_PREVIEW_DIR", "/tmp/q-tonepath-previews"))

BGT_BLOCK = 25
BGT_FLOOR3 = 20
BGT_FLOOR2 = 19

# Compass: N=E5, E=G5, S=D5, W=C5
DIR_NAME = ("up", "right", "down", "left")
DIR_PITCH_FREQ = (1849, 1881, 1825, 1798)  # N E S W
RUNE_ENV = 0xF3
RUNE_ENV_ECHO = 0xF2
RUNE_ENV_FINAL = 0xF7
MISS_ENV1 = 0xA3
MISS_ENV2 = 0x93
MISS_FREQ1 = 1868  # F5
MISS_FREQ2 = 1849  # E5


def ch1_freq(pb):
    return pb.memory[0xFF13] | ((pb.memory[0xFF14] & 7) << 8)


def ch1_env(pb):
    return pb.memory[0xFF12]


def ch4_triggered(pb):
    # NR44 trigger bit. A miss must not write the noise channel.
    return pb.memory[0xFF23] & 0x80


def freq_reg_hz(reg):
    """Game Boy CH1 period register -> Hz."""
    return 131072.0 / (2048 - reg)


def peak_hz(frames, sr):
    """Dominant pitch of one or more PyBoy sound frames (write-only NR13)."""
    if not frames:
        return None
    cat = np.concatenate([np.asarray(f, dtype=np.float64) for f in frames], axis=0)
    mono = cat.mean(axis=1) if cat.ndim == 2 else cat
    mono = mono - mono.mean()
    if np.max(np.abs(mono)) < 1:
        return None
    n = len(mono)
    spec = np.fft.rfft(mono * np.hanning(n))
    mag = np.abs(spec)
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    mag[freqs < 100] = 0
    return float(freqs[int(np.argmax(mag))])


def pitch_close(hz, reg, tol=45.0):
    return hz is not None and abs(hz - freq_reg_hz(reg)) < tol


def find_tone_seed():
    for seed in range(0x1000, 0x20000):
        if puzzle_slot_kind(seed, 0, 1) == PUZZLE_TONE_PATH:
            return seed
    raise RuntimeError("no Stage 1 Waystone tone-path seed in range")


def load_tone_room(seed=None):
    if seed is None:
        seed = find_tone_seed()
    waystone = mission_graph(dungeon_size(0), seed, 0)["waystone"]
    pb = generated_room(0, seed=seed, local_room=waystone, keep_running=True)
    return pb, seed, waystone


def cairn(pb):
    blocks = [(x, y) for y in range(1, 16) for x in range(1, 19)
              if pb.memory[TM + y * 20 + x] == BGT_BLOCK]
    assert len(blocks) == 1, f"expected one cairn, got {blocks}"
    return blocks[0]


def socket(pb):
    return pb.memory[addr("_room_socket_x")], pb.memory[addr("_room_socket_y")]


def shove(pb, direction, expect_move=None):
    """Push once. Returns a dict: moved, missed, freq, env, noise."""
    bx, by = cairn(pb)
    hx, hy = {
        "right": (bx * 8 - 20, by * 8 - 8),
        "left": ((bx + 2) * 8 + 4, by * 8 - 8),
        "down": (bx * 8, by * 8 - 20),
        "up": (bx * 8, (by + 2) * 8 + 4),
    }[direction]
    put16(pb, PL + 9, hx)
    put16(pb, PL + 11, hy)
    pb.memory[0xFF12] = 0
    pb.memory[0xFF23] = 0
    pb.button_press(direction)
    seen_miss = False
    miss_freq = 0
    miss_env = 0
    rune_freq = 0
    rune_env = 0
    noise = 0
    rune_frames = []
    miss1_frames = []
    miss2_frames = []
    sr = pb.sound.sample_rate
    for _ in range(140):
        pb.tick()
        freq, env = ch1_freq(pb), ch1_env(pb)
        frame = np.array(pb.sound.ndarray, copy=True)
        if env in (RUNE_ENV, RUNE_ENV_ECHO, RUNE_ENV_FINAL):
            rune_freq, rune_env = freq, env
            rune_frames.append(frame)
        if freq in (MISS_FREQ1, MISS_FREQ2) or env in (MISS_ENV1, MISS_ENV2):
            seen_miss = True
            miss_freq, miss_env = freq, env
            if env == MISS_ENV1:
                miss1_frames.append(frame)
            elif env == MISS_ENV2:
                miss2_frames.append(frame)
        if pb.memory[0xFF21]:  # NR42 envelope; noise used
            noise = pb.memory[0xFF21]
        if seen_miss or cairn(pb) != (bx, by) or not pb.memory[LOCKED]:
            break
    pb.button_release(direction)
    for _ in range(16):
        pb.tick()
        freq, env = ch1_freq(pb), ch1_env(pb)
        frame = np.array(pb.sound.ndarray, copy=True)
        if env in (RUNE_ENV, RUNE_ENV_ECHO, RUNE_ENV_FINAL):
            rune_freq, rune_env = freq, env
            rune_frames.append(frame)
        if freq in (MISS_FREQ1, MISS_FREQ2) or env in (MISS_ENV1, MISS_ENV2):
            seen_miss = True
            miss_freq, miss_env = freq, env
            if env == MISS_ENV1:
                miss1_frames.append(frame)
            elif env == MISS_ENV2:
                miss2_frames.append(frame)
    after = cairn(pb)
    delta = {"up": (0, -1), "right": (1, 0), "down": (0, 1), "left": (-1, 0)}
    expected = (bx + delta[direction][0], by + delta[direction][1])
    # A miss snap-back returns the crate to the phrase start, which is a
    # different cell than both the shove origin and the intended dest.
    moved = after == expected
    missed = (after != (bx, by) and after != expected) or (
        seen_miss and after != expected)
    if expect_move:
        assert moved or not pb.memory[LOCKED], (
            f"cairn at {bx},{by} would not move {direction}")
    return {"moved": moved, "missed": missed, "freq": rune_freq or ch1_freq(pb),
            "env": rune_env or ch1_env(pb), "miss_freq": miss_freq, "miss_env": miss_env,
            "rune_hz": peak_hz(rune_frames, sr),
            "miss1_hz": peak_hz(miss1_frames, sr),
            "miss2_hz": peak_hz(miss2_frames, sr),
            "noise": noise, "start": (bx, by), "after": after}


def floor2_cells(pb):
    return {(x, y) for y in range(1, 16) for x in range(1, 19)
            if pb.memory[TM + y * 20 + x] == BGT_FLOOR2}


def flash_present(pb, baseline=frozenset()):
    return bool(floor2_cells(pb) - set(baseline))


def test_wrong_push_error_and_reset(pb, frames):
    start = cairn(pb)
    hp = pb.memory[PL + 2]
    missed = False
    for name in DIR_NAME:
        result = shove(pb, name)
        if result["missed"]:
            missed = True
            assert result["noise"] == 0, "miss sting wrote the noise channel"
            assert result["miss_env"] in (MISS_ENV1, MISS_ENV2), (
                f"miss env {result['miss_env']:#x}, want 0xA3/0x93")
            # NR13 is write-only, so pitches come from the sound buffer.
            if result["miss1_hz"] is not None:
                assert pitch_close(result["miss1_hz"], MISS_FREQ1), (
                    f"miss note 1 was {result['miss1_hz']:.1f} Hz, "
                    f"want {freq_reg_hz(MISS_FREQ1):.1f}")
            if result["miss2_hz"] is not None:
                assert pitch_close(result["miss2_hz"], MISS_FREQ2), (
                    f"miss note 2 was {result['miss2_hz']:.1f} Hz, "
                    f"want {freq_reg_hz(MISS_FREQ2):.1f}")
            assert result["miss1_hz"] is not None or result["miss2_hz"] is not None, (
                "miss sting produced no measurable pitch")
            assert cairn(pb) == start
            assert pb.memory[LOCKED] == 1
            assert pb.memory[PL + 2] == hp, "miss charged HP"
            frames.append(pb.screen.image.copy())
            break
        if result["moved"]:
            # Correct first step: miss from here, must snap to original start.
            for name2 in DIR_NAME:
                result2 = shove(pb, name2)
                if result2["missed"] or cairn(pb) == start:
                    missed = True
                    frames.append(pb.screen.image.copy())
                    assert pb.memory[LOCKED] == 1
                    break
            break
    assert missed, "could not provoke a wrong shove"
    assert cairn(pb) == start, "crate was not back at start after the miss"


def test_solve_phrase(pb, frames):
    start = cairn(pb)
    path = []
    for _ in range(4):
        here = cairn(pb)
        found = None
        for name, dir_id in zip(DIR_NAME, range(4)):
            result = shove(pb, name)
            if result["missed"]:
                assert cairn(pb) == start
                replay_path(pb, path)
                here = cairn(pb)
                continue
            if result["moved"] or not pb.memory[LOCKED]:
                if pb.memory[LOCKED]:
                    # Mid-phrase notes use the rune envelope. The last
                    # (tonic) step uses the longer final envelope.
                    want = DIR_PITCH_FREQ[dir_id]
                    assert result["env"] in (RUNE_ENV, RUNE_ENV_FINAL), (
                        f"correct {name} env {result['env']:#x}, want rune")
                    assert pitch_close(result["rune_hz"], want), (
                        f"correct {name} voiced {result['rune_hz']} Hz, "
                        f"want {freq_reg_hz(want):.1f}")
                path.append(name)
                found = name
                frames.append(pb.screen.image.copy())
                break
        assert found is not None, f"no legal shove after {path} at {here}"
        if not pb.memory[LOCKED]:
            break
    assert not pb.memory[LOCKED], f"phrase {path} did not release the seal"
    assert path[-1] == "left", f"cadence shove was {path[-1]}, not west/left"
    sx, sy = socket(pb)
    assert cairn(pb) == (sx, sy), "crate is not seated on the socket"
    assert pb.memory[RS + 27] & 0x80, "Waystone solve did not persist"
    return path


def replay_path(pb, path):
    for name in path:
        here = cairn(pb)
        result = shove(pb, name, expect_move=True)
        assert result["moved"] or not pb.memory[LOCKED]


def test_mid_phrase_reset(pb):
    """Two correct shoves then a miss must return to the original start."""
    start = cairn(pb)
    path_so_far = []
    for step in range(2):
        here = cairn(pb)
        found = None
        for name in DIR_NAME:
            result = shove(pb, name)
            if result["missed"]:
                replay_path(pb, path_so_far)
                here = cairn(pb)
                continue
            if result["moved"]:
                path_so_far.append(name)
                found = name
                break
        assert found, f"could not take correct step {step}"
    assert cairn(pb) != start
    for name in DIR_NAME:
        here = cairn(pb)
        result = shove(pb, name)
        if result["missed"] or cairn(pb) == start:
            assert cairn(pb) == start, "mid-phrase miss did not reset to start"
            assert pb.memory[LOCKED] == 1
            return "reset"
        # A legal later step is fine; keep looking for a miss from the new cell.
    raise AssertionError("mid-phrase miss did not reset to start")


def test_teaser(pb, path):
    """Approaching the socket echoes the solved phrase's compass pitches."""
    sx, sy = socket(pb)
    # Edge-triggered: leave the 2-tile neighbourhood, then re-enter.
    put16(pb, PL + 9, 16)
    put16(pb, PL + 11, 16)
    for _ in range(12):
        pb.tick()
    put16(pb, PL + 9, (sx - 2) * 8)
    put16(pb, PL + 11, sy * 8 - 8)
    pb.memory[0xFF12] = 0
    # Echo envelope stays written between retriggers, so split on the 24-frame
    # teaser gap rather than on env falling low.
    log = []
    sr = pb.sound.sample_rate
    for i in range(24 * 5 + 12):
        pb.tick()
        log.append((ch1_env(pb), np.array(pb.sound.ndarray, copy=True)))
    start = next((i for i, (env, _) in enumerate(log) if env == RUNE_ENV_ECHO), None)
    assert start is not None, "approach teaser never started"
    heard = []
    for n in range(4):
        a = start + n * 24
        b = a + 18
        frames = [frm for env, frm in log[a:b] if env == RUNE_ENV_ECHO]
        heard.append(peak_hz(frames, sr))
    expected = [freq_reg_hz(DIR_PITCH_FREQ[DIR_NAME.index(n)]) for n in path]
    for i, (hz, want) in enumerate(zip(heard, expected)):
        assert hz is not None and abs(hz - want) < 45, (
            f"teaser note {i} was {hz} Hz, want {want:.1f} for path {path} (heard {heard})")


def test_three_miss_flash(pb, baseline=frozenset()):
    start = cairn(pb)
    # Find one consistently wrong direction from the start cell.
    wrong = None
    for name in DIR_NAME:
        result = shove(pb, name)
        if result["missed"]:
            wrong = name
            break
        if result["moved"]:
            # Walked a correct first step; miss to get back, then the
            # opposite of that first step is a start-cell miss.
            first = name
            for name2 in DIR_NAME:
                if shove(pb, name2)["missed"] or cairn(pb) == start:
                    break
            # Any dir except first should miss at start; pick the next.
            wrong = next(n for n in DIR_NAME if n != first)
            # Confirm it misses.
            if not shove(pb, wrong)["missed"]:
                wrong = None
            else:
                # That confirmation already counted as a miss.
                break
    assert wrong, "could not find a wrong first shove"
    misses = 1  # we already landed at least one miss while searching
    while misses < 4:
        result = shove(pb, wrong)
        assert result["missed"], f"{wrong} stopped missing after {misses}"
        misses += 1
    assert flash_present(pb, baseline), "3+ miss did not flash the next 2x2 cell"


def main():
    PREVIEW.mkdir(parents=True, exist_ok=True)
    seed = find_tone_seed()
    print(f"[tone-path] seed=0x{seed:08X}")

    # Room 1: teaser + wrong shove + mid-phrase reset + 3-miss flash, then solve
    pb, seed, waystone = load_tone_room(seed)
    assert pb.memory[KIND] == PUZZLE_TONE_PATH and pb.memory[LOCKED] == 1, (
        f"kind={pb.memory[KIND]} locked={pb.memory[LOCKED]}")
    assert visible_hostiles(pb), "tone-path room looked empty on arrival"
    assert len(active_hostiles(pb)) >= 1, "tone-path room lost its guard pack"
    frames = [pb.screen.image.copy()]
    frames[-1].save(PREVIEW / "tone-path-arrival.png")
    clear_hostiles(pb)
    for _ in range(8):
        pb.tick()
    frames.append(pb.screen.image.copy())
    frames[-1].save(PREVIEW / "tone-path-socket.png")
    sx, sy = socket(pb)
    assert (sx, sy) != (0xFF, 0xFF)
    assert all(
        pb.memory[TM + (sy + dy) * 20 + sx + dx] == BGT_FLOOR3
        for dy in (0, 1) for dx in (0, 1)
    ), "socket is not a visible 2x2 gold plate"
    start = cairn(pb)
    assert start != (sx, sy), "crate already seated on the socket"
    baseline = floor2_cells(pb)

    # Teaser first (before any shove), then we will compare after we know path.
    # We capture teaser after discovering the path on a second boot.

    test_wrong_push_error_and_reset(pb, frames)
    frames[-1].save(PREVIEW / "tone-path-miss.png")

    test_mid_phrase_reset(pb)
    assert cairn(pb) == start

    test_three_miss_flash(pb, baseline)
    frames.append(pb.screen.image.copy())
    frames[-1].save(PREVIEW / "tone-path-hint.png")

    path = test_solve_phrase(pb, frames)
    frames[-1].save(PREVIEW / "tone-path-solved.png")
    print(f"[tone-path] solved path {path}")
    pb.stop(save=False)

    # Fresh room for the approach teaser, using the known path.
    pb, _, _ = load_tone_room(seed)
    clear_hostiles(pb)
    test_teaser(pb, path)
    frames.append(pb.screen.image.copy())
    frames[-1].save(PREVIEW / "tone-path-teaser.png")
    pb.stop(save=False)

    frames[0].save(
        PREVIEW / "tone-path.gif", save_all=True,
        append_images=frames[1:], duration=700, loop=0)
    audio = PREVIEW / "tone-path-audio.txt"
    audio.write_text(
        "Audio description of /tone-path.gif:\n"
        "Arrival: a 2x2 cairn sits off a visible gold socket in a Stage 1 "
        "Waystone court.\n"
        "A wrong shove plays a sour musical double-note (F5 then E5, a "
        "descending minor second, Jeopardy time-out feel — not a noise "
        "buzz) and the crate snaps back to its start.\n"
        "After three misses, the next legal 2x2 cell flashes as a bright "
        "floor tile (luminance hint).\n"
        "The correct path is four compass notes: "
        + " then ".join(path)
        + ". West/left is always the last shove and voices tonic C5, "
        "which holds into the delayed puzzle fanfare as the socket is "
        "seated and the doors open.\n"
        "Approaching the gold socket (or using Echo Chime) plays the same "
        "four-note phrase as a quiet echo so you can learn it by ear.\n"
    )
    print(f"[tone-path] previews in {PREVIEW}")


if __name__ == "__main__":
    main()
