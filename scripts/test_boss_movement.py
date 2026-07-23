#!/usr/bin/env python3
"""ROM regression: early stage bosses must differ in body movement, not bullets."""
from test_boss_identity import EN, PL, enter_boss, put16


def pos(pb, boss):
    return pb.memory[boss + 3], pb.memory[boss + 7]


def main():
    # Stage 2's Serpent must reflect from a wall and continue on the other
    # diagonal, rather than falling back to generic direct pursuit.
    pb, serpent = enter_boss(1, keep_open=True)
    put16(pb, serpent + 3, 10)
    put16(pb, serpent + 7, 10)
    pb.memory[serpent + 15] = 1  # NE
    pb.memory[serpent + 16] = 0
    # Verdant's bounce holds one readable re-engagement beat between moves;
    # sample long enough to observe both the wall reflection and its next
    # diagonal step rather than assuming the old two-frame cadence.
    for _ in range(20):
        pb.tick()
    sx, sy = pos(pb, serpent)
    assert (sx, sy) != (10, 10) and pb.memory[serpent + 15] == 3, (
        f"Serpent did not bounce into a new diagonal: x={sx}, y={sy}, "
        f"dir={pb.memory[serpent + 15]}")
    pb.stop(save=False)

    # Stage 8's Hydra also bounces, but its three staggered projectile lanes
    # need a broad, slower weave—not the Serpent's identical pinball cadence.
    # Force both at a clear central starting point and compare live movement
    # beats over the same window; this catches a future copy/paste of the
    # Serpent divider while allowing normal entity-update frame pacing.
    def bounce_steps(stage):
        pb, boss = enter_boss(stage, keep_open=True)
        put16(pb, boss + 3, 64)
        put16(pb, boss + 7, 48)
        pb.memory[boss + 15] = 1  # NE
        pb.memory[boss + 16] = 0
        samples = []
        for _ in range(60):
            samples.append(pos(pb, boss))
            pb.tick()
        pb.stop(save=False)
        return sum(a != b for a, b in zip(samples, samples[1:]))

    serpent_steps = bounce_steps(1)
    hydra_steps = bounce_steps(7)
    assert hydra_steps >= 2, f"Hydra stopped weaving ({hydra_steps} moves)"
    assert serpent_steps > hydra_steps, (
        f"Hydra copied Serpent bounce cadence: serpent={serpent_steps}, "
        f"hydra={hydra_steps}")

    # Stage 3's Maw performs a two-pixel lunge after its warning. Sampling
    # live frames catches a regression to the old one-pixel shared creep.
    pb, maw = enter_boss(2, keep_open=True)
    put16(pb, PL + 9, 132)
    put16(pb, PL + 11, 64)
    samples = []
    for _ in range(80):
        samples.append(pos(pb, maw))
        pb.tick()
    fastest = max(abs(b[0] - a[0]) + abs(b[1] - a[1])
                  for a, b in zip(samples, samples[1:]))
    assert fastest >= 2, f"Maw never entered its lunge (fastest step={fastest})"

    # Its fast three-lane breath is a wind-up, not a constant bullet tax.
    # Force an immediate volley while its motion state is visibly winding up,
    # then repeat while it is in the lunge. The second probe must leave the
    # recovery lane free for the intended melee punish beat.
    def hostile_shots():
        return sum(pb.memory[EN + i * 28] == 1
                   and pb.memory[EN + i * 28 + 1] & 1
                   and not pb.memory[EN + i * 28 + 1] & 0x10
                   for i in range(32))

    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == 1:
            pb.memory[ep] = pb.memory[ep + 1] = 0
    pb.memory[maw + 15] = 0  # boss motion: wind-up
    pb.memory[maw + 10] = 20 # remain in wind-up after this tick
    pb.memory[maw + 18] = 0  # boss volley timer
    pb.tick()
    assert hostile_shots() == 3, "Maw wind-up lost its fast triple breath"

    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == 1:
            pb.memory[ep] = pb.memory[ep + 1] = 0
    pb.memory[maw + 15] = 1  # boss motion: lunge
    pb.memory[maw + 10] = 8  # remain in lunge after this tick
    pb.memory[maw + 18] = 0
    pb.tick()
    assert hostile_shots() == 0, "Maw fired through its lunge/recovery opening"
    pb.stop(save=False)

    # Stage 4's Spider gets a forced imminent blink; it must relocate a
    # meaningful distance and not blink into collision geometry.
    pb, spider = enter_boss(3, keep_open=True)
    put16(pb, PL + 9, 80)
    put16(pb, PL + 11, 72)
    before = pos(pb, spider)
    pb.memory[spider + 10] = 1  # private blink countdown (vx)
    # The gameplay loop advances its entity table on alternating displayed
    # frames in this harness; allow the countdown and resolved move through.
    for _ in range(4):
        pb.tick()
    after = pos(pb, spider)
    leap = abs(after[0] - before[0]) + abs(after[1] - before[1])
    assert leap >= 20, f"Spider blink did not relocate: {before} -> {after}"
    assert 8 <= after[0] <= 129 and 8 <= after[1] <= 105, (
        f"Spider blink escaped room bounds: {after}")
    flank = max(abs((after[0] + 12) - 80), abs((after[1] + 12) - 72))
    assert flank >= 40, f"Spider blink landed inside its fair flank band: {flank}px"
    assert pb.memory[spider + 18] >= 14, (
        f"Spider fired through its post-blink re-engagement beat: {pb.memory[spider + 18]}")

    # Frost's danger is an alternating normal-speed web plus the blink, not
    # a hidden fast aimed bolt that fills its own lane gap. Force its first
    # volley and pin the exact four readable lanes for the encounter.
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == 1:
            pb.memory[ep] = pb.memory[ep + 1] = 0
    pb.memory[spider + 18] = 0
    pb.memory[spider + 21] = 0
    pb.tick()
    web = []
    for i in range(32):
        ep = EN + i * 28
        if (pb.memory[ep] == 1 and pb.memory[ep + 1] & 1
                and not pb.memory[ep + 1] & 0x10):
            vx, vy = pb.memory[ep + 10], pb.memory[ep + 11]
            web.append((vx - 256 if vx >= 128 else vx,
                        vy - 256 if vy >= 128 else vy))
    assert len(web) == 4 and all(max(abs(vx), abs(vy)) == 2 for vx, vy in web), (
        f"Spider web lost its four normal-speed lanes: {web}")
    pb.stop(save=False)

    # Stage 5's Toxic Mire keeps its six mixed-speed scatter bolts, but must
    # leave a readable 34-frame lane-recovery beat after every spray.
    pb, mire = enter_boss(4, keep_open=True)
    pb.memory[mire + 18] = 0  # boss volley timer
    for _ in range(4):
        pb.tick()
        if pb.memory[mire + 18]:
            break
    assert 30 <= pb.memory[mire + 18] <= 34, (
        f"Mire scatter lost its readable recovery: {pb.memory[mire + 18]}")
    pb.stop(save=False)

    # Hydra retains all five staggered-speed streams, but must not refill the
    # lane faster than its authored 30-frame read-and-cross beat.
    pb, hydra = enter_boss(7, keep_open=True)
    pb.memory[hydra + 18] = 0
    for _ in range(4):
        pb.tick()
        if pb.memory[hydra + 18]:
            break
    assert 26 <= pb.memory[hydra + 18] <= 30, (
        f"Hydra stream recovery lost its lane beat: {pb.memory[hydra + 18]}")
    pb.stop(save=False)

    print(f"[boss-motion] PASS Serpent bounce {serpent_steps} beats; "
          f"Hydra weave {hydra_steps} beats; Maw lunge {fastest}px + punish window; "
          f"Spider blink {leap}px/{flank}px flank + four-lane web; "
          f"Mire recovery 34; Hydra recovery 30")


if __name__ == "__main__":
    main()
