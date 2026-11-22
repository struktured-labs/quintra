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


def font_tiles(text):
    return bytes(0 if char == " " else ord(char) - ord("A") + 11
                 for char in text)


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
            # A legal warm transition may inherit either VRAM bank. Hold the
            # selector on attributes so Game Over must choose tile bank 0
            # before loading its font and drawing, as Pocket hardware requires.
            first.memory[0xFF4F] = 1
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
        bg_map = 0x9C00 if (first.memory[0xFF40] & 0x08) else 0x9800
        # The visor rises and the results text appears at frame 130. Wait
        # for the authored GAME OVER glyphs on row 2 rather than assuming
        # enter() already wrote them.
        game_over = font_tiles("GAME OVER")
        seen = False
        title_at = -1
        for _ in range(240):
            first.tick()
            row2 = bytes(first.memory[bg_map + 2 * 32:bg_map + 2 * 32 + 20])
            title_at = row2.find(game_over)
            if title_at >= 1 and title_at + len(game_over) <= 19:
                seen = True
                break
        assert seen, (
            "game-over never drew GAME OVER in bank-0 font tiles on row 2"
        )
        for _ in range(4):
            first.tick()
        first.memory[0xFF4F] = 1
        attrs = b"".join(
            bytes(first.memory[bg_map + y * 32:bg_map + y * 32 + 20])
            for y in range(18)
        )
        first.memory[0xFF4F] = 0
        # Authored attributes only: palettes 0-4, optional bank-1 and flips,
        # no leftover dungeon priority or unused bits.
        for i, a in enumerate(attrs):
            pal = a & 7
            assert pal <= 4, f"stale or illegal palette {pal} at cell {i}"
            assert (a & 0x90) == 0, f"illegal attribute bits {a:#x} at cell {i}"
        # Every results line stays inside columns 1..18.
        for y in (2, 13, 14, 15, 16):
            row = bytes(first.memory[bg_map + y * 32:bg_map + y * 32 + 20])
            assert row[0] == 0 and row[19] == 0, (
                f"row {y} used a margin column: {list(row)}"
            )
        title_attrs = attrs[2 * 20 + title_at:2 * 20 + title_at + len(game_over)]
        assert all((a & 0x0F) == 3 for a in title_attrs), (
            f"GAME OVER must use title palette 3 in bank 0: {list(title_attrs)}"
        )
        easy_hint = font_tiles("TRY EASY MODE")
        row13 = bytes(first.memory[bg_map + 13 * 32:bg_map + 13 * 32 + 20])
        hint_at = row13.find(easy_hint)
        assert hint_at >= 1 and hint_at + len(easy_hint) <= 19, (
            f"Normal game-over omitted Easy-mode recovery hint: {list(row13)}"
        )
        hint_attrs = attrs[13 * 20 + hint_at:13 * 20 + hint_at + len(easy_hint)]
        assert all((a & 0x0F) == 4 for a in hint_attrs), (
            f"hint must use gold palette 4 in bank 0: {list(hint_attrs)}"
        )
        # The visor well (rows 4-12, cols 5-14) must actually use bank-1 art.
        well = []
        for y in range(4, 13):
            well.extend(attrs[y * 20 + 5:y * 20 + 15])
        assert any(a & 0x08 for a in well), "game-over visor was not drawn in VRAM bank 1"

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

        # Exercise the real in-process restart before the separate cold-boot
        # proof. The title, audio master, and title score must recover without
        # relying on emulator power-on register defaults.
        press(first, "start")
        for _ in range(30):
            first.tick()
        assert first.memory[SCREEN] == 1, "warm death restart missed title"
        warm_title = font_tiles("QUINTRA")
        assert bytes(first.memory[
            0x9800 + 4 * 32 + 6:0x9800 + 4 * 32 + 6 + len(warm_title)
        ]) == warm_title, "warm death restart produced a black title"
        assert first.memory[TRACK] == 18, "warm death restart missed title music"
        assert first.memory[0xFF26] & 0x80, "warm death restart disabled audio"

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
        # Erase one hero and one enemy tile in bank 0, then deliberately leave
        # VBK on bank 1 while choosing the hero. Room entry must restore bank 0
        # before its atlas uploads or Pocket renders those actors black.
        second.memory[0xFF4F] = 0
        for address in (*range(0x8000, 0x8040), *range(0x8140, 0x8150)):
            second.memory[address] = 0
        second.memory[0xFF4F] = 1
        press(second, "a")
        for _ in range(80):
            second.tick()
        assert second.memory[SCREEN] == 5, "could not start clean run after death"
        second.memory[0xFF4F] = 0
        assert any(second.memory[0x8000:0x8040]), \
            "room loaded the hero atlas into CGB VRAM bank 1"
        assert any(second.memory[0x8140:0x8150]), \
            "room loaded the enemy atlas into CGB VRAM bank 1"
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
