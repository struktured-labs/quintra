#!/usr/bin/env python3
"""Live-ROM contract for stage-transition vignettes (spec 2026-11-16 §2).

Triggers each implemented vignette through the real seams (a new-game
foyer into Crystal Caverns, a Riftwild gate portal into Verdant Hollow and
Ember Depths, a defeated boss's south door into the Riftwild, and the
Worldglass shift into Hollow), then checks:
  * the vignette screen plays (~3 s) and returns to the room,
  * A/B/START skip from frame 8,
  * play-once per run (the second entry falls back to the stage card),
  * CUTSCENES OFF (PACK aim page, LEFT/RIGHT) suppresses it,
  * every borrowed BG tile is restored after the room resumes.
GIFs from the real ROM go to builds/vignettes-<sha8>/ (160x144 and 4x), or
to $QUINTRA_VIGNETTE_GIF_DIR.
"""
import os
os.environ["QUINTRA_KEEP_VIGNETTES"] = "1"

import hashlib
import os
import sys
from pathlib import Path

from pyboy import PyBoy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_stage_states import (  # noqa: E402
    BGT_DOOR, BGT_PORTAL, DIR_NONE, ROOM_H, ROOM_W, boot_to_stage,
    normalize_compact_source, riftwild_return_screen, solve_entry_puzzle,
    symbol_addresses,
)
from quintra_topology import STAGE_BOSS_ROOM, STAGE_START, dungeon_entry_room  # noqa: E402
from quintra_vignettes import VIGNETTE_SEEN_OFFSET, seen_address  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ROM = Path(os.environ.get("QUINTRA_TEST_ROM", ROOT / "rom/working/quintra.gbc")).resolve()
A = symbol_addresses(ROM)
RS, PL, EN, TM = A["_run_state"], A["_player"], A["_entities"], A["_room_tilemap"]
SCREEN = A["_loop_current_screen"]
NOI = ROM.with_suffix(".noi").read_text()
# IDs from src/render/vignette_data.h. Crystal/Verdant are appended so
# the already-shipped Ember id stays 2.
VIG_RIFT_WAKING, VIG_RIFT_HOLLOW, VIG_STAGE_EMBER = 0, 1, 2
VIG_STAGE_CRYSTAL, VIG_STAGE_VERDANT = 3, 4
VIG_STAGE_FROST, VIG_STAGE_MIRE, VIG_STAGE_SHADOW = 5, 6, 7
VIG_STAGE_GOLDEN, VIG_STAGE_BLOODMOON, VIG_STAGE_VOID = 8, 9, 10
SEEN = seen_address(ROM)  # run_state.vignette_seen (u16, saved with the run)
SCREEN_ROOM, SCREEN_VIGNETTE, SCREEN_INVENTORY, SCREEN_DIALOG = 5, 6, 9, 10
WAYGEAR_OWNED, RIFTWILD_SHADOW = 44, 57
SHA = hashlib.sha256(ROM.read_bytes()).hexdigest()
OUT = Path(os.environ.get("QUINTRA_VIGNETTE_GIF_DIR", ROOT / "builds" / f"vignettes-{SHA[:8]}"))
GATE_SCREEN = (8, 21, 34)


def seen_byte(pb, vig_id, sram=False):
    """Low or high byte of vignette_seen (WRAM, or the run record in SRAM)."""
    if sram:
        base = 0xA000 + 5 + VIGNETTE_SEEN_OFFSET
        return pb.memory[0, base + (1 if vig_id >= 8 else 0)]
    return pb.memory[SEEN + (1 if vig_id >= 8 else 0)]


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def tap(pb, key, hold=4, after=8):
    pb.button_press(key)
    pb.tick(hold)
    pb.button_release(key)
    pb.tick(after)


def boot(consume_start=True):
    """Title + class select. Stage 1's foyer vignette starts from run_init_tick;
    consume it (no GIF) unless the caller is the stage 1 contract.
    """
    pb = PyBoy(str(ROM), window="null", cgb=True)
    pb.tick(240)
    tap(pb, "start", after=30)
    pb.button_press("a")
    pb.tick(4)
    pb.button_release("a")
    # run_init_tick returns SCREEN_VIGNETTE (or ROOM if muted / already seen).
    got = wait_screen(pb, (SCREEN_VIGNETTE, SCREEN_ROOM), 240)
    if consume_start and got == SCREEN_VIGNETTE:
        play_through(pb, [])
        got = pb.memory[SCREEN]
        # The foyer vignette now exits through a fresh room_enter (procgen,
        # spawn, music) instead of the resume path; let the new room settle.
        pb.tick(60)
        got = pb.memory[SCREEN]
    if consume_start:
        assert got == SCREEN_ROOM, f"boot did not reach the room ({got})"
        # Stage 1's seen bit is expected; high byte still clear.
        assert pb.memory[SEEN] & (1 << VIG_STAGE_CRYSTAL)
        assert pb.memory[SEEN + 1] == 0
    return pb


def bg_tiles(pb):
    """VRAM bank 0 BG tile data 0x8800-0x97FF (both signed halves)."""
    return bytes(pb.memory[0, 0x8800:0x9800])


def portal_into_stage(pb, stage, seed=0xF07E0011):
    """Stand on a Riftwild gate portal leading into `stage` (0-based)."""
    target = dungeon_entry_room(stage, seed)
    pb.memory[RS + 1] = STAGE_START[stage] - 1
    for offset, byte in enumerate(seed.to_bytes(4, "little")):
        pb.memory[RS + 2 + offset] = byte
    pb.memory[RS + 6] = 0xFF
    pb.memory[RS + 11] = stage
    pb.memory[RS + 12] = pb.memory[RS + 13] = 0
    pb.memory[RS + 17] = 1
    pb.memory[RS + 18] = GATE_SCREEN[(stage - 1) % 3]
    pb.memory[RS + 47] = 0x80 | (1 << (2 + ((stage - 1) % 3)))
    for slot in range(32):
        base = EN + slot * 28
        pb.memory[base] = pb.memory[base + 1] = 0
    normalize_compact_source(pb, A)
    put16(pb, PL + 9, 72)
    put16(pb, PL + 11, 60)
    pb.memory[TM + 9 * ROOM_W + 10] = BGT_PORTAL
    for _ in range(90):
        pb.tick()
        if pb.memory[RS + 1] == target:
            break
    assert pb.memory[RS + 1] == target, f"could not enter stage {stage + 1}"


def wait_screen(pb, want, limit=300):
    for _ in range(limit):
        if pb.memory[SCREEN] in want:
            return pb.memory[SCREEN]
        pb.tick()
    return pb.memory[SCREEN]


def play_through(pb, frames, skip_at=None):
    """Run the vignette screen to completion; returns frames spent in it."""
    spent = 0
    while pb.memory[SCREEN] == SCREEN_VIGNETTE and spent < 400:
        if skip_at is not None and spent == skip_at:
            pb.button_press("a")
        if skip_at is not None and spent == skip_at + 3:
            pb.button_release("a")
        pb.memory[PL + 15] = 200
        pb.tick()
        spent += 1
        frames.append(pb.screen.image.copy())
    if skip_at is not None:
        pb.button_release("a")
    for _ in range(30):
        pb.tick()
        frames.append(pb.screen.image.copy())
    return spent


def save_gif(frames, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fr = [f.convert("RGB") for f in frames[::2]]
    fr[0].save(OUT / f"{name}.gif", save_all=True, append_images=fr[1:],
               duration=33, loop=0, optimize=False)
    big = [f.resize((640, 576), 0) for f in fr]
    big[0].save(OUT / f"{name}-4x.gif", save_all=True, append_images=big[1:],
                duration=33, loop=0, optimize=False)


def lit(img, box):
    """Fraction of non-dark pixels in box."""
    px = list(img.convert("RGB").crop(box).getdata())
    return sum(1 for p in px if sum(p) > 120) / len(px)


def check_vignette_frames(frames, start, label):
    mid = frames[start + 90]
    assert lit(mid, (24, 8, 136, 104)) > 0.3, f"{label}: picture not shown"
    assert lit(mid, (0, 120, 160, 136)) > 0.04, f"{label}: name/motto missing"
    assert lit(frames[start + 3], (0, 0, 160, 144)) < 0.05, \
        f"{label}: vignette did not start from black"


def ember_contract():
    pb = boot()
    try:
        frames = []
        portal_into_stage(pb, 2)
        got = wait_screen(pb, (SCREEN_VIGNETTE, SCREEN_DIALOG), 240)
        assert got == SCREEN_VIGNETTE, \
            f"Ember Depths entry did not play its vignette (screen {got})"
        before = bg_tiles(pb)
        # The seen bit rides in the run suspend (SRAM bank 0 run record:
        # 5-byte header, then run_state), so save-and-quit cannot replay it.
        saved = pb.memory[0, 0xA000 + 5 + VIGNETTE_SEEN_OFFSET]
        assert saved & (1 << VIG_STAGE_EMBER), f"seen bit not saved ({saved:#x})"
        frames.append(pb.screen.image.copy())
        spent = play_through(pb, frames)
        assert 180 <= spent <= 250, f"Ember vignette length {spent} frames"
        assert pb.memory[SCREEN] == SCREEN_ROOM, "vignette did not resume the room"
        save_gif(frames, "stage3-ember-depths")
        check_vignette_frames(frames, 0, "ember")
        # Borrowed BG tiles must be restored; ignore tiles the live room
        # animates by itself (lava/water cycles).
        after = bg_tiles(pb)
        animated = set()
        prev = after
        for _ in range(120):
            pb.memory[PL + 15] = 200
            pb.tick()
            cur = bg_tiles(pb)
            animated |= {i // 16 for i in range(len(cur)) if cur[i] != prev[i]}
            prev = cur
        broken = sorted({i // 16 for i in range(len(after))
                         if after[i] != before[i]} - animated)
        assert not broken, f"BG tiles not restored after vignette: {broken}"
        # Play once per run: a second Ember entry gets the classic card.
        portal_into_stage(pb, 2)
        got = wait_screen(pb, (SCREEN_VIGNETTE, SCREEN_DIALOG), 240)
        assert got == SCREEN_DIALOG, f"second Ember entry replayed vignette ({got})"
    finally:
        pb.stop(save=False)
    print(f"[vignettes] ember: plays {spent} frames, restores VRAM, once per run")


def skip_contract():
    pb = boot()
    try:
        portal_into_stage(pb, 2)
        assert wait_screen(pb, (SCREEN_VIGNETTE,), 240) == SCREEN_VIGNETTE
        # A held through the black load (before frame 8) must not skip.
        frames = []
        pb.button_press("a")
        pb.tick(4)
        pb.button_release("a")
        pb.tick(2)
        assert pb.memory[SCREEN] == SCREEN_VIGNETTE, "skip fired before frame 8"
        spent = play_through(pb, frames, skip_at=24)
        # 16-frame exit fade plus the room resume rebuild (about 30-40 frames).
        assert spent <= 24 + 40, f"A skip took {spent} frames"
        assert pb.memory[SCREEN] == SCREEN_ROOM
    finally:
        pb.stop(save=False)
    print(f"[vignettes] skip: A at frame 24 returned after {spent} frames")


def cutscenes_off_contract():
    pb = boot()
    try:
        tap(pb, "start", after=20)
        assert pb.memory[SCREEN] == SCREEN_INVENTORY
        tap(pb, "select", after=20)
        tap(pb, "right", after=20)
        OUT.mkdir(parents=True, exist_ok=True)
        pb.screen.image.save(OUT / "pack-cutscenes-off.png")
        assert pb.memory[1, 0xA00B] & 0x04, "CUTSCENES OFF not saved"
        tap(pb, "b", after=30)
        assert pb.memory[SCREEN] == SCREEN_ROOM
        portal_into_stage(pb, 2)
        got = wait_screen(pb, (SCREEN_VIGNETTE, SCREEN_DIALOG), 240)
        assert got == SCREEN_DIALOG, "CUTSCENES OFF still played a vignette"
    finally:
        pb.stop(save=False)
    print("[vignettes] CUTSCENES OFF suppresses vignettes and is saved in SRAM")


def cross_to_riftwild(pb, after_stage):
    solve_entry_puzzle(pb, A)
    target = STAGE_BOSS_ROOM[after_stage - 1]
    pb.memory[RS + 1] = target
    pb.memory[RS + 6] = DIR_NONE
    pb.memory[RS + 10] = 0
    pb.memory[RS + 12] = pb.memory[RS + 13] = 0
    pb.memory[RS + 17] = 0
    pb.memory[RS + 18] = pb.memory[RS + 19] = 0
    pb.memory[RS + 20] = 0
    pb.memory[RS + 21] = pb.memory[RS + 22] = 0
    normalize_compact_source(pb, A)
    for i in range(32):
        entity = EN + i * 28
        if pb.memory[entity] == 2:
            pb.memory[entity] = pb.memory[entity + 1] = 0
    pb.memory[TM + (ROOM_H - 1) * ROOM_W + 9] = BGT_DOOR
    pb.memory[TM + (ROOM_H - 1) * ROOM_W + 10] = BGT_DOOR
    put16(pb, PL + 9, 72)
    put16(pb, PL + 11, 120)
    pb.button_press("down")
    try:
        for _ in range(240):
            pb.tick()
            if pb.memory[RS + 17] and pb.memory[SCREEN] != SCREEN_ROOM:
                break
    finally:
        pb.button_release("down")
    assert pb.memory[RS + 17] == 1
    assert pb.memory[RS + 18] == riftwild_return_screen(after_stage)


def shift(pb, frames):
    # Hold the chord a few frames: the Riftwild main loop can run slower
    # than one game tick per frame, so a 1-frame press may be missed.
    pb.button_press("select")
    pb.button_press("b")
    for _ in range(4):
        pb.tick()
    pb.button_release("select")
    pb.button_release("b")
    for _ in range(200):
        pb.memory[PL + 15] = 120
        pb.tick()
        frames.append(pb.screen.image.copy())
        if pb.memory[SCREEN] == SCREEN_VIGNETTE:
            return SCREEN_VIGNETTE
    return pb.memory[SCREEN]


def riftwild_contract():
    pb, _ram, _room = boot_to_stage(ROM, A, 1, "normal", 0)
    try:
        pb.memory[SEEN] = pb.memory[SEEN + 1] = 0
        cross_to_riftwild(pb, 1)
        got = wait_screen(pb, (SCREEN_VIGNETTE,), 240)
        assert got == SCREEN_VIGNETTE, f"Riftwild entry played no vignette ({got})"
        frames = [pb.screen.image.copy()]
        spent = play_through(pb, frames)
        assert 180 <= spent <= 250, f"Riftwild vignette length {spent}"
        assert pb.memory[SCREEN] == SCREEN_ROOM and pb.memory[RS + 17] == 1
        check_vignette_frames(frames, 0, "riftwild")
        save_gif(frames, "riftwild-enter")

        # First Worldglass shift into Hollow plays the Hollow variant.
        pb.memory[PL + WAYGEAR_OWNED] |= 1 << 3
        for _ in range(60):
            pb.memory[PL + 15] = 120
            pb.tick()
        got = shift(pb, [])
        assert got == SCREEN_VIGNETTE, (
            f"first Hollow shift: screen {got} shadow "
            f"{pb.memory[RS + RIFTWILD_SHADOW]:#x} seen {pb.memory[SEEN]:#x}")
        assert pb.memory[RS + RIFTWILD_SHADOW] & 1
        frames = [pb.screen.image.copy()]
        spent = play_through(pb, frames)
        assert pb.memory[SCREEN] == SCREEN_ROOM
        check_vignette_frames(frames, 0, "hollow")
        save_gif(frames, "riftwild-enter-hollow")
        # Back to Waking, then Hollow again: no replay this run.
        for _ in range(2):
            for _ in range(60):
                pb.memory[PL + 15] = 120
                pb.tick()
            got = shift(pb, [])
            assert got == SCREEN_ROOM, f"repeat shift replayed a vignette ({got})"
    finally:
        pb.stop(save=False)
    print("[vignettes] riftwild: Waking on entry, Hollow on first shift, once each")


def skip_with(pb, key, skip_at=24):
    """Skip the current vignette with A, B or START; return frames spent."""
    frames = []
    spent = 0
    while pb.memory[SCREEN] == SCREEN_VIGNETTE and spent < 400:
        if spent == skip_at:
            pb.button_press(key)
        if spent == skip_at + 3:
            pb.button_release(key)
        pb.memory[PL + 15] = 200
        pb.tick()
        spent += 1
        frames.append(pb.screen.image.copy())
    pb.button_release(key)
    for _ in range(30):
        pb.tick()
        frames.append(pb.screen.image.copy())
    return spent, frames


def crystal_contract():
    pb = boot(consume_start=False)
    try:
        got = wait_screen(pb, (SCREEN_VIGNETTE, SCREEN_ROOM), 240)
        assert got == SCREEN_VIGNETTE, \
            f"new-game foyer did not play Crystal Caverns (screen {got})"
        saved = pb.memory[0, 0xA000 + 5 + VIGNETTE_SEEN_OFFSET]
        assert saved & (1 << VIG_STAGE_CRYSTAL), f"seen bit not saved ({saved:#x})"
        frames = [pb.screen.image.copy()]
        spent = play_through(pb, frames)
        assert 180 <= spent <= 250, f"Crystal vignette length {spent} frames"
        assert pb.memory[SCREEN] == SCREEN_ROOM, "vignette did not resume the room"
        save_gif(frames, "stage1-crystal-caverns")
        check_vignette_frames(frames, 0, "crystal")
        # Re-entering the same foyer mid-run must not replay it.
        # The pending flag is one-shot; a later room_enter of the foyer
        # with run_timer > 0 also must not queue it.
        assert pb.memory[SEEN] & (1 << VIG_STAGE_CRYSTAL)
    finally:
        pb.stop(save=False)
    print(f"[vignettes] crystal: plays {spent} frames on new-game foyer")


def verdant_contract():
    pb = boot()
    try:
        frames = []
        portal_into_stage(pb, 1)
        got = wait_screen(pb, (SCREEN_VIGNETTE, SCREEN_DIALOG), 240)
        assert got == SCREEN_VIGNETTE, \
            f"Verdant Hollow entry did not play its vignette (screen {got})"
        frames.append(pb.screen.image.copy())
        spent = play_through(pb, frames)
        assert 180 <= spent <= 250, f"Verdant vignette length {spent} frames"
        assert pb.memory[SCREEN] == SCREEN_ROOM
        save_gif(frames, "stage2-verdant-hollow")
        check_vignette_frames(frames, 0, "verdant")
        portal_into_stage(pb, 1)
        got = wait_screen(pb, (SCREEN_VIGNETTE, SCREEN_DIALOG), 240)
        assert got == SCREEN_DIALOG, f"second Verdant entry replayed vignette ({got})"
    finally:
        pb.stop(save=False)

    print(f"[vignettes] verdant: plays {spent} frames, once per run")


LATER = (
    (3, VIG_STAGE_FROST, "stage4-frost-vault", "frost"),
    (4, VIG_STAGE_MIRE, "stage5-toxic-mire", "mire"),
    (5, VIG_STAGE_SHADOW, "stage6-shadow-keep", "shadow"),
    (6, VIG_STAGE_GOLDEN, "stage7-golden-temple", "golden"),
    (7, VIG_STAGE_BLOODMOON, "stage8-bloodmoon", "bloodmoon"),
    (8, VIG_STAGE_VOID, "stage9-void-sanctum", "void"),
)


def later_stage_contract(stage, vig_id, gif_name, label):
    """Riftwild-to-dungeon arrival for stages 4-9 (0-based stage index)."""
    pb = boot()
    try:
        frames = []
        portal_into_stage(pb, stage)
        got = wait_screen(pb, (SCREEN_VIGNETTE, SCREEN_DIALOG), 240)
        assert got == SCREEN_VIGNETTE, \
            f"{label} entry did not play its vignette (screen {got})"
        saved = seen_byte(pb, vig_id, sram=True)
        assert saved & (1 << (vig_id & 7)), f"{label} seen bit not saved ({saved:#x})"
        frames.append(pb.screen.image.copy())
        spent = play_through(pb, frames)
        assert 180 <= spent <= 250, f"{label} vignette length {spent} frames"
        assert pb.memory[SCREEN] == SCREEN_ROOM, f"{label} did not resume the room"
        save_gif(frames, gif_name)
        check_vignette_frames(frames, 0, label)
        # Re-entry falls back to the stage card (play-once).
        portal_into_stage(pb, stage)
        got = wait_screen(pb, (SCREEN_VIGNETTE, SCREEN_DIALOG, SCREEN_ROOM), 240)
        assert got != SCREEN_VIGNETTE, f"{label} replayed on the second entry"
        print(f"[vignettes] {label}: plays {spent} frames, once per run")
    finally:
        pb.stop(save=False)


def start_skip_contract():
    """START (and B) skip from frame 8, same as A. Uses the new-game foyer."""
    results = {}
    for key in ("start", "b"):
        pb = boot(consume_start=False)
        try:
            assert wait_screen(pb, (SCREEN_VIGNETTE,), 240) == SCREEN_VIGNETTE
            # Held through the black load must not skip.
            pb.button_press(key)
            pb.tick(4)
            pb.button_release(key)
            pb.tick(2)
            assert pb.memory[SCREEN] == SCREEN_VIGNETTE, \
                f"{key} skip fired before frame 8"
            spent, frames = skip_with(pb, key, skip_at=24)
            assert spent <= 24 + 40, f"{key} skip took {spent} frames"
            assert pb.memory[SCREEN] == SCREEN_ROOM
            if key == "start":
                save_gif(frames, "stage1-start-skip")
            results[key] = spent
        finally:
            pb.stop(save=False)
    print(f"[vignettes] skip: START at frame 24 returned after {results['start']} "
          f"frames, B after {results['b']}")


def main():
    crystal_contract()
    verdant_contract()
    ember_contract()
    for args in LATER:
        later_stage_contract(*args)
    skip_contract()
    start_skip_contract()
    cutscenes_off_contract()
    riftwild_contract()
    print(f"[vignettes] PASS gifs in {OUT}")


if __name__ == "__main__":
    main()
