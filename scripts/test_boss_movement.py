#!/usr/bin/env python3
"""ROM regression: early stage bosses must differ in body movement, not bullets."""
from test_boss_identity import EN, PL, enter_boss, put16


def pos(pb, boss):
    return pb.memory[boss + 3], pb.memory[boss + 7]


def main():
    # Stage 2's Serpent now plays Snake: it reaches a cardinal corner, turns
    # east, and never cuts diagonally across its tightening spiral.
    pb, serpent = enter_boss(1, keep_open=True)
    put16(pb, serpent + 3, 64)
    put16(pb, serpent + 7, 48)
    pb.memory[serpent + 15] = 0
    pb.memory[serpent + 16] = 0
    pb.memory[serpent + 21] = 0
    serpent_before = pos(pb, serpent)
    samples = []
    for _ in range(240):
        pb.memory[PL + 15] = 255
        samples.append(pos(pb, serpent))
        pb.tick()
    sx, sy = pos(pb, serpent)
    serpent_after = (sx, sy)
    deltas = [(abs(b[0] - a[0]), abs(b[1] - a[1]))
              for a, b in zip(samples, samples[1:])]
    assert all(not (dx and dy) for dx, dy in deltas), (
        "Serpent cut diagonally instead of following cardinal spiral legs")
    assert min(y for _, y in samples) <= 17, (
        f"Serpent never reached its first north corner: {serpent_before}->{serpent_after}")
    assert max(x for x, _ in samples) >= 90, (
        f"Serpent never turned east after its first corner: {serpent_after}")
    assert len({x for x, _ in samples}) >= 8 and len({y for _, y in samples}) >= 8, (
        "Serpent spiral lost one of its axes")
    pb.stop(save=False)

    # Stage 8's Hydra retains the late-game wall weave as its independent
    # movement gimmick.
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

    hydra_steps = bounce_steps(7)
    assert hydra_steps >= 2, f"Hydra stopped weaving ({hydra_steps} moves)"

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
    web = []
    for _ in range(20):
        pb.tick()
        web = []
        for i in range(32):
            ep = EN + i * 28
            if (pb.memory[ep] == 1 and pb.memory[ep + 1] & 1
                    and not pb.memory[ep + 1] & 0x10):
                vx, vy = pb.memory[ep + 10], pb.memory[ep + 11]
                web.append((vx - 256 if vx >= 128 else vx,
                            vy - 256 if vy >= 128 else vy))
        if web:
            break
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

    print(f"[boss-motion] PASS Serpent cardinal spiral "
          f"{serpent_before}->{serpent_after}; "
          f"Hydra weave {hydra_steps} beats; Maw lunge {fastest}px + punish window; "
          f"Spider blink {leap}px/{flank}px flank + four-lane web; "
          f"Mire recovery 34; Hydra recovery 30")


if __name__ == "__main__":
    main()
