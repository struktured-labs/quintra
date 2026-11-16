#!/usr/bin/env python3
"""Live-ROM contract: unreadable or stale battery SRAM never blocks boot.

Flash carts (EverDrive GB) key .srm files by ROM file name, so a new build
can inherit a months-old or uninitialised 32KB image. Every such image must
reach the title screen, and anything that is not a well-formed suspend must
be treated as "no save" rather than resumed.
"""
import io
import random
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
SRAM_SIZE = 32 * 1024
SCREEN_TITLE = 1
SCREEN_ROOM = 5


def addr(name):
    m = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not m:
        raise RuntimeError(f"missing symbol {name}")
    return int(m.group(1), 16)


SCREEN = addr("_loop_current_screen")


def record(rs, pl, payload_byte=None, good_sum=True, rng=None):
    if rng is not None:
        payload = bytes(rng.randrange(256) for _ in range(rs + pl))
    else:
        payload = bytes(((payload_byte or 0),)) * (rs + pl)
    s = sum(payload) & 0xFF
    if not good_sum:
        s ^= 0x5A
    return b"QS" + bytes((1, rs, pl)) + payload + bytes((s,))


def stale_v1_record():
    run = bytearray(48)
    run[6] = 0xFF      # safe centre arrival
    player = bytearray(44)
    player[0:9] = bytes((0, 8, 8, 6, 6, 4, 2, 5, 2))
    player[24:40] = bytes((0xFF,)) * 16
    payload = bytes(run + player)
    return b"QS" + bytes((1, 48, 44)) + payload + bytes((sum(payload) & 0xFF,))


def image(head=b"", fill=0xFF, bank1=b""):
    img = bytearray((fill,)) * SRAM_SIZE
    img[: len(head)] = head
    img[0x2000 : 0x2000 + len(bank1)] = bank1
    return bytes(img)


def boots_to_title(name, sram):
    pb = PyBoy(str(ROM), window="null", cgb=True, ram_file=io.BytesIO(sram))
    try:
        for _ in range(600):
            pb.tick()
            if pb.memory[SCREEN] == SCREEN_TITLE:
                break
        assert pb.memory[SCREEN] == SCREEN_TITLE, f"{name}: never reached title"
        # A rejected image must not offer CONTINUE: A on the title stays put.
        pb.tick(120)
        pb.button_press("a"); pb.tick(4); pb.button_release("a")
        pb.tick(240)
        return pb.memory[SCREEN]
    finally:
        pb.stop(save=False)


def main():
    rng = random.Random(0x51)
    cases = [
        ("all 0xFF (fresh flash-cart SRAM)", image(fill=0xFF), False),
        ("all 0x00", image(fill=0x00), False),
        ("QS header, bad checksum", image(record(48, 44, 7, good_sum=False)), False),
        ("QS header, absurd lengths", image(b"QS\x01\xff\xff" + bytes(600)), False),
        ("QS wrong version", image(b"QS\x09\x30\x2c" + bytes(200)), False),
        ("QM garbage meta only", image(bank1=b"QM\x02" + bytes(rng.randrange(256) for _ in range(13))), False),
        # Shape of the 2016-stamped EverDrive quintra..srm: v1, 48/44 bytes.
        ("stale v1 48/44 suspend", image(stale_v1_record(), bank1=b"QM\x02\xac\x12\x07\x00\x00\x00\xff\xff\xc3"), True),
    ]
    for seed in range(4):
        r = random.Random(seed)
        cases.append((f"random noise seed {seed}", bytes(r.randrange(256) for _ in range(SRAM_SIZE)), False))
    for name, sram, resumable in cases:
        screen = boots_to_title(name, sram)
        if resumable:
            assert screen == SCREEN_ROOM, f"{name}: continue went to {screen}"
        else:
            assert screen != SCREEN_ROOM, f"{name}: garbage SRAM was resumed as a run"
        print(f"[sram-garbage] ok  {name} -> screen {screen}")
    print("[sram-garbage] PASS garbage/stale SRAM boots to title")


if __name__ == "__main__":
    main()
