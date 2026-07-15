#!/usr/bin/env python3
"""Validate the physical-cartridge-facing Game Boy header and checksums."""
import sys
from pathlib import Path

LOGO = bytes.fromhex(
    "CEED6666CC0D000B03730083000C000D0008111F8889000E"
    "DCCC6EE6DDDDD999BBBB67636E0EECCCDDDC999FBBB9333E"
)


def fail(message):
    raise SystemExit(f"[cartridge] FAIL: {message}")


def main(path):
    rom = Path(path).read_bytes()
    if len(rom) != 64 * 1024:
        fail(f"expected current 64 KiB image, got {len(rom)} bytes")
    if rom[0x104:0x134] != LOGO:
        fail("Nintendo boot-logo block is invalid")
    title = rom[0x134:0x143].split(b"\0", 1)[0]
    if title != b"QUINTRA":
        fail(f"header title is {title!r}, expected b'QUINTRA'")
    expected = {
        0x143: (0xC0, "CGB-only flag"),
        0x147: (0x1B, "MBC5+RAM+battery mapper"),
        0x148: (0x01, "64 KiB ROM size code"),
        0x149: (0x03, "32 KiB RAM size code"),
    }
    for offset, (value, label) in expected.items():
        if rom[offset] != value:
            fail(f"{label} at 0x{offset:03X} is 0x{rom[offset]:02X}, expected 0x{value:02X}")
    header_sum = 0
    for byte in rom[0x134:0x14D]:
        header_sum = (header_sum - byte - 1) & 0xFF
    if header_sum != rom[0x14D]:
        fail(f"header checksum 0x{rom[0x14D]:02X}, calculated 0x{header_sum:02X}")
    global_sum = (sum(rom) - rom[0x14E] - rom[0x14F]) & 0xFFFF
    stored_global = int.from_bytes(rom[0x14E:0x150], "big")
    if global_sum != stored_global:
        fail(f"global checksum 0x{stored_global:04X}, calculated 0x{global_sum:04X}")
    print("[cartridge] PASS QUINTRA, CGB-only, MBC5+32KiB battery RAM, checksums valid")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        fail("usage: check_cartridge.py path/to/quintra.gbc")
    main(sys.argv[1])
