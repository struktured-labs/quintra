#!/usr/bin/env python3
"""Battery-SRAM suspend survives a true emulator process restart."""
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


RS, PL, EN, SCREEN = map(
    addr, ("_run_state", "_player", "_entities", "_loop_current_screen")
)


def press(pb, button, held=4, released=4):
    pb.button_press(button)
    for _ in range(held):
        pb.tick()
    pb.button_release(button)
    for _ in range(released):
        pb.tick()


def boot_fresh(pb):
    for _ in range(240):
        pb.tick()
    press(pb, "start")
    for _ in range(30):
        pb.tick()
    press(pb, "a")
    for _ in range(60):
        pb.tick()


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = value >> 8


def main():
    with tempfile.TemporaryDirectory(prefix="quintra-cart-") as td:
        cart = Path(td) / "quintra.gbc"
        battery = Path(td) / "quintra.sav"
        shutil.copy2(ROM, cart)

        first = PyBoy(str(cart), window="null", cgb=True)
        boot_fresh(first)
        put16(first, PL + 16, 321)       # distinctive persisted player value
        put16(first, RS + 14, 0x1234)   # distinctive persisted run value
        for i in range(32):
            ep = EN + i * 28
            if first.memory[ep] == 2:
                first.memory[ep] = first.memory[ep + 1] = 0
        # Dungeon zero's guaranteed maze spine begins eastward (cell 0→1).
        # The old compact topology opened south here, so pinning that obsolete
        # threshold could no longer exercise the room-entry SRAM transaction.
        put16(first, PL + 9, 144)
        put16(first, PL + 11, 60)
        for _ in range(60):
            first.tick()
            if first.memory[RS + 1] == 1:
                break
        assert first.memory[RS + 1] == 1, "could not create room-entry suspend"
        # The counter changes near the beginning of room_enter(). Wait on the
        # actual SRAM payload rather than a host-frame delay: reachability work
        # deliberately makes room-generation duration layout-dependent.
        saved = False
        for _ in range(240):
            first.tick()
            first.memory[0x0000] = 0x0A
            first.memory[0x4000] = 0
            rs_len = first.memory[0xA003]
            run_off = 0xA005
            player_off = run_off + rs_len
            saved = (
                bytes(first.memory[0xA000:0xA002]) == b"QS"
                and first.memory[run_off + 1] == 1
                and first.memory[run_off + 14] == 0x34
                and first.memory[run_off + 15] == 0x12
                and first.memory[player_off + 16] == 0x41
                and first.memory[player_off + 17] == 0x01
            )
            first.memory[0x0000] = 0
            if saved:
                break
        assert saved, "room-entry SRAM transaction did not commit"
        assert first.memory[RS + 1] == 1, "room advanced again during suspend setup"

        # Inspect the cartridge bytes, not merely the C globals.
        first.memory[0x0000] = 0x0A
        first.memory[0x4000] = 0
        assert bytes(first.memory[0xA000:0xA002]) == b"QS", "suspend magic missing"
        first.memory[0x0000] = 0
        battery_io = battery.open("w+b")
        first.stop(save=True, ram_file=battery_io)
        battery_io.flush()
        assert battery.exists() and battery.stat().st_size >= 32 * 1024, \
            "emulator did not emit the 32 KiB battery image"
        battery_io.seek(0)
        assert battery_io.read(2) == b"QS", "battery image did not preserve suspend magic"

        # A new emulator instance is a power cycle. PyBoy reloads the copied
        # cartridge's battery file exactly as a flash cart/repro board would.
        battery_io.seek(0)
        second = PyBoy(str(cart), window="null", cgb=True, ram_file=battery_io)
        for _ in range(240):
            second.tick()
        press(second, "a")              # title's CONTINUE action
        for _ in range(60):
            second.tick()
        assert second.memory[SCREEN] == 5, "cold boot did not resume SCREEN_ROOM"
        coins = second.memory[PL + 16] | (second.memory[PL + 17] << 8)
        score = second.memory[RS + 14] | (second.memory[RS + 15] << 8)
        assert second.memory[RS + 1] == 1, (
            f"room counter did not survive power cycle "
            f"(room={second.memory[RS + 1]}, coins={coins}, score=0x{score:04X})"
        )
        assert coins == 321, f"player payload drifted across power cycle: {coins}"
        assert score == 0x1234, f"run payload drifted across power cycle: 0x{score:04X}"
        second.stop(save=False)
        battery_io.close()
    print("[suspend] PASS battery SRAM room/player payload survives cold boot")


if __name__ == "__main__":
    main()
