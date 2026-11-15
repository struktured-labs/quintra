#!/usr/bin/env python3
"""Live-ROM: boss drops stay in the room for the rest of the visit.

Ordinary enemy drops still expire on the four-second clock. A cleared
colossus reward must still be on the floor after more than 60 seconds,
without exhausting the 32-slot entity table or the 40-entry OAM.
"""
from test_boss_identity import EN, PL, enter_boss
from test_boss_rewards import (
    ENTITY_SIZE, ENT_PICKUP, PICKUP_COIN_5, PICKUP_HEART_HALF, PICKUP_ITEM,
    setup_projectile,
)

PICKUP_COIN_1 = 1
PICKUP_VISIT_PERSIST_MARK = 0x40
HOLD_FRAMES = 60 * 60 + 60  # 61 seconds, past any old 4s/12s clocks


def pickup_slots(pb):
    slots = []
    for index in range(32):
        address = EN + index * ENTITY_SIZE
        if pb.memory[address] == ENT_PICKUP and (pb.memory[address + 1] & 1):
            slots.append({
                "index": index,
                "addr": address,
                "kind": pb.memory[address + 17],
                "timer": pb.memory[address + 16],
                "mark": pb.memory[address + 24],
                "oam": pb.memory[address + 27],
            })
    return slots


def kinds(slots):
    return sorted(slot["kind"] for slot in slots)


def assert_boss_rewards(slots, label):
    found = kinds(slots)
    hearts = found.count(PICKUP_HEART_HALF)
    coins = found.count(PICKUP_COIN_5)
    relics = found.count(PICKUP_ITEM)
    assert hearts >= 2, f"{label}: missing boss hearts {found}"
    assert coins >= 2, f"{label}: missing boss coins {found}"
    assert relics >= 1, f"{label}: missing boss relic {found}"
    rewards = [slot for slot in slots
               if slot["kind"] in (PICKUP_HEART_HALF, PICKUP_COIN_5, PICKUP_ITEM)]
    assert all(slot["mark"] & PICKUP_VISIT_PERSIST_MARK for slot in rewards), (
        f"{label}: boss rewards were not marked persistent: {rewards}")


def count_oam(pb):
    used = 0
    for slot in range(40):
        y = pb.memory[0xFE00 + slot * 4]
        if 0 < y < 160:
            used += 1
    return used


def free_entity_slots(pb):
    return sum(
        1 for index in range(32)
        if not (pb.memory[EN + index * ENTITY_SIZE + 1] & 1)
    )


def inject_ordinary_coin(pb):
    """Place an unmarked coin far from the hero so only its timer can retire it."""
    for index in range(32):
        address = EN + index * ENTITY_SIZE
        if pb.memory[address + 1] & 1:
            continue
        pb.memory[address] = ENT_PICKUP
        pb.memory[address + 1] = 0x03  # EF_ACTIVE | EF_ALIVE
        pb.memory[address + 3] = 16    # x
        pb.memory[address + 7] = 16    # y
        pb.memory[address + 14] = 1    # hp
        pb.memory[address + 16] = 240  # ordinary 4-second drop clock
        pb.memory[address + 17] = PICKUP_COIN_1
        pb.memory[address + 24] = 0
        pb.memory[address + 25] = 0x66
        return address
    raise AssertionError("no free entity slot for the ordinary drop")


def main():
    pb, boss = enter_boss(0, keep_open=True)
    boss_x, boss_y = pb.memory[boss + 3], pb.memory[boss + 7]
    # Leave the hero at full health and far from the corpse so hearts and
    # coins can sit untouched for the long hold.
    pb.memory[PL + 2] = pb.memory[PL + 1]
    pb.memory[PL + 9] = 144
    pb.memory[PL + 11] = 112
    pb.memory[boss + 14] = 1
    shot = next(EN + index * ENTITY_SIZE for index in range(32)
                if EN + index * ENTITY_SIZE != boss)
    setup_projectile(pb, shot, boss_x, boss_y, player_owned=True)
    for _ in range(20):
        pb.tick()

    slots = pickup_slots(pb)
    assert_boss_rewards(slots, "just after kill")
    ordinary = inject_ordinary_coin(pb)
    assert pb.memory[ordinary] == ENT_PICKUP, "ordinary coin was not injected"

    for _ in range(300):
        pb.tick()
    slots = pickup_slots(pb)
    assert_boss_rewards(slots, "after 5 seconds")
    assert pb.memory[ordinary] == 0 or not (pb.memory[ordinary + 1] & 1), (
        "ordinary enemy drop still lingered past its 4-second clock")
    assert PICKUP_COIN_1 not in kinds(slots), (
        f"ordinary coin was treated as a boss reward: {kinds(slots)}")

    remaining = HOLD_FRAMES - 20 - 300
    for _ in range(remaining):
        pb.tick()
        # Keep the hero parked in case a later room beat tries to walk.
        pb.memory[PL + 9] = 144
        pb.memory[PL + 11] = 112

    slots = pickup_slots(pb)
    assert_boss_rewards(slots, "after 61 seconds")
    assert len(slots) == 5, f"unexpected leftover pickups after the hold: {kinds(slots)}"
    oam = count_oam(pb)
    free = free_entity_slots(pb)
    assert oam < 40, f"persistent drops exhausted OAM: {oam} in-range sprites"
    assert free >= 20, f"persistent drops exhausted entity slots: {32 - free} live"
    # Unique OAM slots among the five rewards when they are on-screen.
    reward_oam = [slot["oam"] for slot in slots if slot["oam"]]
    assert len(reward_oam) == len(set(reward_oam)), (
        f"boss rewards share OAM slots: {reward_oam}")
    pb.stop(save=False)
    print(f"[boss-drop-persist] PASS 61s hold; oam={oam} free_slots={free}")


if __name__ == "__main__":
    main()
