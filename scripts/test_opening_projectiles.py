#!/usr/bin/env python3
"""Live-ROM contract for Normal-mode weak-enemy projectile pressure."""

from test_performance import EN, PL, addr, boot_room, put32


ANIM = addr("_entity_anim_counter")


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def main():
    pb = boot_room()
    try:
        for i in range(32):
            ep = EN + i * 28
            pb.memory[ep] = 0
            pb.memory[ep + 1] = 0

        # One real Flutterbat at slot zero. Counter zero is its authored stagger
        # beat, allowing the cartridge AI—not a test-side projectile fixture—
        # to create the volley.
        flutterbat = EN
        pb.memory[flutterbat] = 2
        pb.memory[flutterbat + 1] = 0x07
        put32(pb, flutterbat + 2, 48 << 8)
        put32(pb, flutterbat + 6, 48 << 8)
        pb.memory[flutterbat + 12] = 73
        pb.memory[flutterbat + 13] = 0
        pb.memory[flutterbat + 14] = 6
        pb.memory[flutterbat + 17] = 12
        pb.memory[flutterbat + 25] = 0xAA
        pb.memory[flutterbat + 26] = 1
        put16(pb, PL + 9, 112)
        put16(pb, PL + 11, 88)
        shots = []
        for _ in range(30):
            # A host VBlank need not contain a complete cartridge update in a
            # dense CGB frame. Hold the authored phase until AI consumes it.
            pb.memory[ANIM] = (-49 * 29) & 0xFF
            pb.tick()
            shots = [EN + i * 28 for i in range(32)
                     if pb.memory[EN + i * 28] == 1
                     and pb.memory[EN + i * 28 + 1] & 1]
            if shots:
                break
        assert len(shots) == 3, \
            f"weak Normal enemy emitted {len(shots)} shots, expected a 3-way volley"
        for shot in shots:
            vx = pb.memory[shot + 10]
            vy = pb.memory[shot + 11]
            vx = vx - 256 if vx > 127 else vx
            vy = vy - 256 if vy > 127 else vy
            assert max(abs(vx), abs(vy)) == 1, \
                f"opening projectile is not slow: {(vx, vy)}"
            assert pb.memory[shot + 16] >= 170, \
                "opening projectile did not retain its long-lived lane: " \
                f"ttl={pb.memory[shot + 16]}"
            assert pb.memory[shot + 13] == 4, \
                "opening projectile lost its warm danger palette"
    finally:
        pb.stop(save=False)

    print("[opening-projectiles] PASS staggered 3-way slow lingering Normal volley")


if __name__ == "__main__":
    main()
