"""Shared PyBoy helper: keep stage-transition vignettes out of other contracts.

Vignettes play the first time per run a dungeon or the Riftwild is entered
(scripts/test_stage_vignettes.py owns that behavior). Gameplay fixtures that
cross those seams for other reasons must pre-mark every vignette as seen
during SCREEN_RUN_INIT, before the first room tick. Waiting until after
class-select settle ticks lets the stage 1 foyer vignette start and breaks
timing contracts. boot_to_stage and mute_after_class_select already do this.
"""
import re
from pathlib import Path

# offsetof(run_state_t, vignette_seen): appended u16 after shop_civic (59).
VIGNETTE_SEEN_OFFSET = 60
SCREEN_TITLE = 1
SCREEN_RUN_INIT = 3
SCREEN_ROOM = 5
SCREEN_VIGNETTE = 6


def _symbol(rom, name):
    noi = Path(rom).with_suffix(".noi").read_text()
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", noi)
    return int(match.group(1), 16) if match else None



def reach_title(pb, rom, limit=600, min_ticks=240):
    """Reach the title, then idle to at least `min_ticks` power-on frames.

    Power-on can land in the lore intro for well over 240 frames, so a
    fixed tick(240) never sees the title when sitecustomize is off (#224).
    When the intro is already skipped, keep the historical 240-frame
    settle so CI fixtures stay on the same DIV timeline as before.
    """
    screen = _symbol(rom, "_loop_current_screen")
    ticks = 0
    if screen is None:
        for _ in range(max(min_ticks, 0)):
            pb.tick()
        return
    while ticks < limit:
        if pb.memory[screen] == SCREEN_TITLE and ticks >= min_ticks:
            return
        pb.tick()
        ticks += 1
    if pb.memory[screen] == SCREEN_TITLE:
        return
    pb.button_press("start")
    pb.tick(4)
    pb.button_release("start")
    for _ in range(180):
        if pb.memory[screen] == SCREEN_TITLE:
            return
        pb.tick()


def seen_address(rom):
    addr = _symbol(rom, "_run_state")
    return addr + VIGNETTE_SEEN_OFFSET


def mute_vignettes(pb, rom):
    """Mark every vignette seen and drop a queued new-run foyer play."""
    addr = seen_address(rom)
    pb.memory[addr] = pb.memory[addr + 1] = 0xFF
    pending = _symbol(rom, "_room_start_vignette")
    if pending is not None:
        pb.memory[pending] = 0


def mute_after_class_select(pb, rom, settle=0):
    """Confirm has already been pressed. Mute as soon as run_state exists.

    Ticks until SCREEN_RUN_INIT, ROOM, or VIGNETTE (or 30 frames), mutes,
    then optionally settles a further `settle` frames. If a vignette already
    started, it is skipped with START once frame 8 of the play has passed.
    """
    screen = _symbol(rom, "_loop_current_screen")
    muted = False
    for _ in range(30):
        if screen is not None and pb.memory[screen] in (
                SCREEN_RUN_INIT, SCREEN_ROOM, SCREEN_VIGNETTE):
            mute_vignettes(pb, rom)
            muted = True
            break
        pb.tick()
    if not muted:
        mute_vignettes(pb, rom)
    if screen is not None and pb.memory[screen] == SCREEN_VIGNETTE:
        # Too late to un-arm; skip so the room is ready for the caller.
        for _ in range(16):
            pb.tick()
        pb.button_press("start")
        pb.tick(4)
        pb.button_release("start")
        for _ in range(50):
            pb.tick()
            if pb.memory[screen] == SCREEN_ROOM:
                break
    for _ in range(settle):
        pb.tick()
