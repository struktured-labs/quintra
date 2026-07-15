#!/usr/bin/env python3
"""Post-link ROM layout guard.

The ASxxxx linker will happily place code past the end of the GB address
space (or leave banking machinery stranded in a switchable bank) without
erroring. That failure mode shipped six boot-broken commits: the flat
32KB image overflowed, _GSINIT landed at 0x88xx, and boot jumped into
the void -> white screen. This script fails the build instead.

Checks (banked build):
  1. Home-ish areas (_CODE, _HOME, _GSINIT, _GSFINAL, _INITIALIZER,
     _LIT, _BASE) must end at or below 0x8000. (_CODE spilling past
     0x4000 into the bank-1 window is tolerated only while nothing
     switches banks; with -autobank, home must fit bank 0 -- warn hard.)
  2. ___sdcc_bcall_ehl (the banked-call trampoline) must live < 0x4000.
     If it's in the switchable window it unmaps itself on bank switch.
  3. The ROM must have >= 3 populated banks (autobank actually worked;
     a broken flag set collapses everything to banks 0-1).
  4. Every fixed switchable _CODE_N area must fit its 16 KiB bank. The
     linker only warns when one crosses into the next bank, producing a ROM
     that can pass header tests while containing overwritten code.
"""
import re
import sys

def fail(msg):
    print(f"[layout] FAIL: {msg}")
    sys.exit(1)

def main(stem):
    map_path, noi_path, rom_path = stem + ".map", stem + ".noi", stem + ".gbc"

    # ---- 1. area extents from the .map
    worst_home_end = 0
    try:
        text = open(map_path).read()
    except OSError as e:
        fail(f"cannot read {map_path}: {e}")
    for m in re.finditer(
        r"^(_CODE|_HOME|_GSINIT|_GSFINAL|_INITIALIZER|_LIT|_BASE)\s+"
        r"([0-9A-Fa-f]{8})\s+([0-9A-Fa-f]{8})\s+=", text, re.M):
        name, addr, size = m.group(1), int(m.group(2), 16), int(m.group(3), 16)
        end = addr + size
        if end > 0x8000:
            fail(f"area {name} ends at 0x{end:04X} -- past the 0x8000 ROM "
                 f"window. Code/init would execute from open bus at boot.")
        worst_home_end = max(worst_home_end, end)

    # Fixed bank areas are reported with linearized addresses (bank N at
    # N*0x10000 + 0x4000), but their size must still never exceed 0x4000.
    for m in re.finditer(
        r"^(_CODE_(\d+))\s+([0-9A-Fa-f]{8})\s+([0-9A-Fa-f]{8})\s+=",
        text, re.M):
        name, size = m.group(1), int(m.group(4), 16)
        if size > 0x4000:
            fail(f"area {name} is {size} bytes -- overflows its 16 KiB "
                 "switchable bank by {size - 0x4000} bytes")

    # ---- 2. trampoline must be in bank 0
    try:
        noi = open(noi_path).read()
    except OSError as e:
        fail(f"cannot read {noi_path}: {e}")
    m = re.search(r"DEF\s+___sdcc_bcall_ehl\s+0x([0-9A-Fa-f]+)", noi)
    if m:
        addr = int(m.group(1), 16)
        if addr >= 0x4000:
            fail(f"___sdcc_bcall_ehl at 0x{addr:04X} -- banked-call "
                 f"trampoline in the SWITCHABLE window. Home code must "
                 f"shrink below 16KB (playbook 2026-07-05, section 4).")
        tramp = f"0x{addr:04X}"
    else:
        tramp = "absent (no banked calls?)"

    # ---- 3. banks actually populated
    try:
        rom = open(rom_path, "rb").read()
    except OSError as e:
        fail(f"cannot read {rom_path}: {e}")
    banks = [b for b in range(len(rom) // 0x4000)
             if sum(1 for x in rom[b * 0x4000:(b + 1) * 0x4000]
                    if x not in (0, 0xFF)) > 16]
    if len(banks) < 3:
        fail(f"only banks {banks} populated -- autobank collapsed "
             f"(check for a stray -Wm-yo flag; playbook section 5).")

    print(f"[layout] OK: home ends 0x{worst_home_end:04X}, "
          f"trampoline {tramp}, banks {banks}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        fail("usage: check_rom_layout.py <path/stem-without-extension>")
    main(sys.argv[1])
