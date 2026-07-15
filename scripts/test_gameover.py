#!/usr/bin/env python3
"""ROM contract: real combat death is permanent across a cartridge restart."""
import re
import shutil
import tempfile
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


RS, PL, EN, SCREEN, TRACK = map(
    addr,
    ("_run_state", "_player", "_entities", "_loop_current_screen", "_music_track_id"),
)


def press(pb, button, held=4, released=4):
    pb.button_press(button)
    for _ in range(held):
        pb.tick()
    pb.button_release(button)
    for _ in range(released):
        pb.tick()


def put_fix8(pb, address, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (i * 8)) & 0xFF


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def boot_fresh_run(pb):
    for _ in range(240):
        pb.tick()
    press(pb, "start")
    for _ in range(30):
        pb.tick()
    press(pb, "a")
    for _ in range(80):
        pb.tick()
    assert pb.memory[SCREEN] == 5, "fresh cartridge did not enter SCREEN_ROOM"


def main():
    with tempfile.TemporaryDirectory(prefix="quintra-death-") as td:
        cart = Path(td) / "quintra.gbc"
        battery = Path(td) / "quintra.sav"
        shutil.copy2(ROM, cart)

        first = PyBoy(str(cart), window="null", cgb=True)
        boot_fresh_run(first)

        # room_enter must already have made a valid suspend before the fatal hit.
        first.memory[0x0000] = 0x0A
        first.memory[0x4000] = 0
        assert bytes(first.memory[0xA000:0xA002]) == b"QS", \
            "fresh room has no suspend record to invalidate"
        first.memory[0x0000] = 0

        # Distinct values make the game-over/meta assertions authoritative.
        put16(first, RS + 14, 4321)
        put16(first, RS + 6, 123)
        first.memory[RS + 16] = 7
        first.memory[PL + 2] = 1
        first.memory[PL + 15] = 0

        # Deliver a fatal hostile projectile through combat_resolve(), then let
        # the cartridge play its complete 50-frame death beat into GAMEOVER.
        px = first.memory[PL + 9] | (first.memory[PL + 10] << 8)
        py = first.memory[PL + 11] | (first.memory[PL + 12] << 8)
        projectile = next(
            EN + i * 28 for i in range(32) if not (first.memory[EN + i * 28 + 1] & 1)
        )
        for i in range(28):
            first.memory[projectile + i] = 0
        first.memory[projectile] = 1       # ENT_PROJECTILE
        first.memory[projectile + 1] = 3   # active + alive, hostile
        # Aim at the 6x6 center-of-mass hurtbox. The hero's head may legally
        # overhang a wall, so top-left injection can despawn against cover.
        put_fix8(first, projectile + 2, px + 5)
        put_fix8(first, projectile + 6, py + 9)
        first.memory[projectile + 14] = 1
        first.memory[projectile + 16] = 20
        first.memory[projectile + 25] = 0x77
        first.memory[projectile + 26] = 4

        for _ in range(180):
            first.tick()
            if first.memory[SCREEN] == 11:
                break
        assert first.memory[SCREEN] == 11, (
            f"fatal combat never entered SCREEN_GAMEOVER: screen={first.memory[SCREEN]} "
            f"hp={first.memory[PL + 2]} projectile="
            f"{first.memory[projectile]}/{first.memory[projectile + 1]} "
            f"player={px},{py} shot={first.memory[projectile + 3]},"
            f"{first.memory[projectile + 7]}"
        )
        # The dispatcher publishes the new screen id immediately before its
        # banked enter() finishes drawing, recording SRAM, and starting audio.
        enter_frames = 0
        for enter_frames in range(1, 241):
            first.tick()
            if first.memory[TRACK] == 20:
                break
        assert first.memory[PL + 2] == 0, "game-over did not preserve empty HP"
        assert first.memory[TRACK] == 20, (
            f"game-over did not request track 20: track={first.memory[TRACK]}"
        )
        assert enter_frames <= 120, \
            f"game-over entry remained blank too long: {enter_frames} frames"

        first.memory[0x0000] = 0x0A
        first.memory[0x4000] = 0
        assert first.memory[0xA000] != ord("Q"), "death left suspend magic valid"
        first.memory[0x4000] = 1
        assert bytes(first.memory[0xA000:0xA002]) == b"QM", \
            "death did not initialize meta records"
        best = first.memory[0xA003] | (first.memory[0xA004] << 8)
        runs = first.memory[0xA005] | (first.memory[0xA006] << 8)
        wins = first.memory[0xA007] | (first.memory[0xA008] << 8)
        assert (best, runs, wins) == (4321, 1, 0), \
            f"death meta drifted: best/runs/wins={(best, runs, wins)}"
        first.memory[0x0000] = 0

        battery_io = battery.open("w+b")
        first.stop(save=True, ram_file=battery_io)
        battery_io.flush()

        # A true restart must retain records but offer no CONTINUE action.
        battery_io.seek(0)
        second = PyBoy(str(cart), window="null", cgb=True, ram_file=battery_io)
        for _ in range(240):
            second.tick()
        assert second.memory[SCREEN] == 1, "cold boot did not reach title"
        press(second, "a")
        assert second.memory[SCREEN] == 1, "dead run resumed after power cycle"

        second.memory[0x0000] = 0x0A
        second.memory[0x4000] = 1
        persisted_runs = second.memory[0xA005] | (second.memory[0xA006] << 8)
        assert persisted_runs == 1, "death record did not survive power cycle"
        second.memory[0x0000] = 0

        press(second, "start")
        for _ in range(30):
            second.tick()
        press(second, "a")
        for _ in range(80):
            second.tick()
        assert second.memory[SCREEN] == 5, "could not start clean run after death"
        second.memory[0x0000] = 0x0A
        second.memory[0x4000] = 0
        assert bytes(second.memory[0xA000:0xA002]) == b"QS", \
            "replacement run did not create a fresh suspend"
        second.memory[0x0000] = 0
        second.stop(save=False)
        battery_io.close()

    print(
        f"[gameover] PASS fatal combat + {enter_frames}f entry + "
        "permadeath power cycle + clean restart"
    )


if __name__ == "__main__":
    main()
