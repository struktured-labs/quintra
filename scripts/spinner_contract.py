"""Shared live-ROM contract for the Spinner family (Sunwheel, Bramble, Halo).

Since #3 a Spinner no longer fires an instant opposite pair. When its cadence
expires it arms a 64-frame told spiral: one shot every eight frames, stepping
one compass point per shot in its orbit direction, so the volley sweeps a full
ring one lane at a time instead of flooding it.
"""
import math

ENTITY_SIZE = 28
ENT_PROJECTILE = 1
EF_ACTIVE, EF_ON_SCREEN, EF_PLAYER_PROJ = 0x01, 0x04, 0x10
SPIRAL_SHOTS = 8
SPIRAL_STEP = 8
TRACK_AGE = 6      # read heading before the wave's sideways swing


def _put_fix8(pb, address, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (i * 8)) & 0xFF


def _put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def _s16(pb, address):
    value = pb.memory[address] | pb.memory[address + 1] << 8
    return value - 0x10000 if value & 0x8000 else value


def _hostile_slots(pb, en):
    slots = {}
    for i in range(32):
        ep = en + i * ENTITY_SIZE
        flags = pb.memory[ep + 1]
        if (pb.memory[ep] == ENT_PROJECTILE and flags & EF_ACTIVE
                and not flags & EF_PLAYER_PROJ):
            slots[i] = (_s16(pb, ep + 3), _s16(pb, ep + 7))
    return slots


def assert_told_spiral(pb, ep, en, pl, tm, label):
    """Isolate the live spinner at ``ep`` and measure one whole volley."""
    for i in range(32):
        other = en + i * ENTITY_SIZE
        if other != ep:
            pb.memory[other] = pb.memory[other + 1] = 0
    for i in range(20 * 17):
        pb.memory[tm + i] = 1
    _put_fix8(pb, ep + 2, 64)
    _put_fix8(pb, ep + 6, 64)
    pb.memory[ep + 1] |= EF_ON_SCREEN
    pb.memory[ep + 16] = 2     # body divider: one measured orbit step
    pb.memory[ep + 18] = 0     # ai_data[1]: cadence expired, arm now
    pb.memory[ep + 19] = 0     # ai_data[2]: spiral starts due north
    pb.memory[ep + 21] = 0     # ai_data[4]: no volley already in flight
    clockwise = pb.memory[ep + 20] & 1
    _put16(pb, pl + 9, 112)
    _put16(pb, pl + 11, 64)

    births = {}      # slot -> (tick, x, y)
    tracks = {}      # slot -> last (x, y)
    per_tick = []
    known = set()
    for tick in range(SPIRAL_SHOTS * SPIRAL_STEP + 2 + TRACK_AGE):
        pb.tick()
        live = _hostile_slots(pb, en)
        fresh = [s for s in live if s not in known]
        per_tick.append(len(fresh))
        for s in fresh:
            births[(s, tick)] = live[s]
        known = set(live)
        for s, pos in live.items():
            key = max((k for k in births if k[0] == s), key=lambda k: k[1])
            if tick - key[1] <= TRACK_AGE:
                tracks[key] = pos
    shots = sorted(births, key=lambda k: k[1])
    assert len(shots) == SPIRAL_SHOTS, (
        f"{label} spiral fired {len(shots)} shots, not {SPIRAL_SHOTS}")
    assert max(per_tick) == 1, f"{label} fired a burst, not a told spiral"
    gaps = {b[1] - a[1] for a, b in zip(shots, shots[1:])}
    assert gaps == {SPIRAL_STEP}, f"{label} spiral cadence drifted: {gaps}"

    sectors = []
    for key in shots:
        x, y = tracks[key]
        bx, by = births[key]
        angle = math.degrees(math.atan2(x - bx, by - y)) % 360   # 0 = north
        sectors.append(int(((angle + 22.5) % 360) // 45))
    assert len(set(sectors)) == SPIRAL_SHOTS, (
        f"{label} spiral repeated a lane: {sectors}")
    step = 1 if clockwise else 7
    turns = {(b - a) % 8 for a, b in zip(sectors, sectors[1:])}
    assert turns == {step}, f"{label} spiral does not sweep in order: {sectors}"
    return sectors
