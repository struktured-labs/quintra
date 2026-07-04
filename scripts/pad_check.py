#!/usr/bin/env python3
"""8BitDo / gamepad binding checker for mGBA.

Watches all input interfaces of the controller and decodes what each
physical press actually emits (js axis / js button / hat / keyboard key),
then says whether mGBA's GB bindings will catch it.

Usage:  python3 scripts/pad_check.py   (then press buttons; Ctrl-C to stop)
"""

import os
import select
import struct
import sys
import time

JS_DEV = "/dev/input/js0"
EV_DEVS = ["/dev/input/event14", "/dev/input/event15", "/dev/input/event16"]

EV_KEY, EV_ABS = 0x01, 0x03

# js0 interface: hats appear as high-numbered axes (6/7 typically)
AXIS_NAMES = {
    0: "left-stick X", 1: "left-stick Y",
    2: "right-stick X", 3: "right-stick Y",
    4: "trigger L2", 5: "trigger R2",
    6: "D-PAD X (hat)", 7: "D-PAD Y (hat)",
}
BTN_NAMES = {
    0: "B(south)", 1: "A(east)", 2: "Y(west)... or X", 3: "X(north)... or Y",
    4: "L1", 5: "R1", 6: "Select/minus", 7: "Start/plus",
    8: "Home", 9: "L3", 10: "R3",
}

def main():
    fds = {}
    try:
        fds[os.open(JS_DEV, os.O_RDONLY | os.O_NONBLOCK)] = ("js0", 8)
    except OSError as e:
        print(f"can't open {JS_DEV}: {e}")
    for p in EV_DEVS:
        try:
            fds[os.open(p, os.O_RDONLY | os.O_NONBLOCK)] = (p.split("/")[-1], 24)
        except OSError:
            pass
    if not fds:
        print("no readable input devices — is the dongle plugged in?")
        sys.exit(1)

    print("watching:", ", ".join(v[0] for v in fds.values()))
    print("PRESS BUTTONS on the pad (Ctrl-C to finish)...\n")

    summary = set()
    try:
        while True:
            r, _, _ = select.select(list(fds), [], [], 0.25)
            for fd in r:
                label, esz = fds[fd]
                try:
                    data = os.read(fd, 4096)
                except OSError:
                    continue
                for off in range(0, len(data) - esz + 1, esz):
                    if label == "js0":
                        _, val, typ, num = struct.unpack_from("IhBB", data, off)
                        if typ & 0x80:
                            continue
                        if typ & 0x01:
                            name = BTN_NAMES.get(num, f"btn{num}")
                            print(f"[js0] BUTTON {num:<2} ({name}) -> {val}")
                            if val:
                                summary.add(f"button {num}")
                        elif typ & 0x02 and abs(val) > 8000:
                            name = AXIS_NAMES.get(num, f"axis{num}")
                            print(f"[js0] AXIS   {num:<2} ({name}) -> {val:+d}")
                            summary.add(f"axis {num}")
                    else:
                        _, _, typ, code, val = struct.unpack_from("qqHHi", data, off)
                        if typ == EV_KEY and val == 1:
                            print(f"[{label}] KEY code={code} (KEYBOARD-MODE press!)")
                            summary.add(f"kbd key {code}")
    except KeyboardInterrupt:
        pass

    print("\n--- verdict ---")
    if not summary:
        print("NOTHING received. Pad is asleep/off or paired elsewhere.")
        print("Wake it (hold Start), check the dongle pairing, re-run.")
        return
    print("saw:", ", ".join(sorted(summary)))
    if any(s.startswith("axis 6") or s.startswith("axis 7") for s in summary):
        print("D-pad emits HAT events -> mGBA auto-binds these. GOOD.")
    if any(s.startswith("axis 0") or s.startswith("axis 1") for s in summary):
        print("Left stick on axes 0/1 -> bound in gb.input.SDLC. GOOD.")
    if any(s.startswith("kbd") for s in summary):
        print("WARNING: controller is in KEYBOARD mode — switch it to")
        print("X-input (hold pairing combo / flip mode switch) for mGBA.")

if __name__ == "__main__":
    main()
