#!/usr/bin/env python3
"""Bombs cost 2 MP and refuse a throw the bar cannot afford."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if (ROOT / "scripts").is_dir():
    sys.path.insert(0, str(ROOT / "scripts"))
else:
    sys.path.insert(0, str(ROOT))

from test_will_max import (  # noqa: E402
    PLAYER as P, ENTITIES as E, boot, clear_arena, put16, addr,
)

ITEM_BOMBS = 48
AUX_BOMB = 0xF7
ENTITY_SIZE = 28
BOMB_MP_COST = 2
CLASS_PICSEAN = 3
CLASS_SAURAN = 1
LIMITLESS = 2


def bombs_live(pb):
    return [
        E + i * ENTITY_SIZE
        for i in range(32)
        if pb.memory[E + i * ENTITY_SIZE] == 1
        and pb.memory[E + i * ENTITY_SIZE + 23] == AUX_BOMB
    ]


def fire_right(pb):
    pb.button_press("right")
    pb.button_press("b")
    pb.tick(2)
    pb.button_release("b")
    pb.button_release("right")
    pb.tick(1)


def settle_regen(pb):
    """Advance until one trickle tick, so the next is ~96–144 frames away."""
    if pb.memory[P + 3] < 8:
        pb.memory[P + 3] = 8
    pb.memory[P + 4] = 1
    prev = 1
    for _ in range(200):
        pb.tick(1)
        mp = pb.memory[P + 4]
        if mp > prev:
            return
        prev = mp
    raise AssertionError("trickle regen did not fire within 200 frames")


def scene(class_id):
    pb = boot(class_id)
    clear_arena(pb)
    pb.memory[addr("_entity_enemy_count")] = 0
    pb.memory[P + 24] = ITEM_BOMBS
    pb.memory[P + 18] = ITEM_BOMBS
    pb.memory[P + 19] = 0
    pb.memory[P + 13] = 1  # FACE_E
    put16(pb, P + 9, 64)
    put16(pb, P + 11, 72)
    pb.memory[P + 1] = 20
    pb.memory[P + 2] = 20
    pb.memory[P + 15] = 200
    pb.tick(2)
    settle_regen(pb)
    pb.memory[P + 19] = 0
    return pb


def arm_mp(pb, mp, mp_max=None):
    if mp_max is not None:
        pb.memory[P + 3] = mp_max
    pb.memory[P + 4] = mp
    pb.memory[P + 19] = 0
    pb.memory[P + 24] = ITEM_BOMBS
    pb.memory[P + 18] = ITEM_BOMBS


class TestBombMpCost(unittest.TestCase):
    def test_throw_spends_two_mp(self):
        pb = scene(CLASS_PICSEAN)
        arm_mp(pb, 10, 10)
        fire_right(pb)
        self.assertEqual(len(bombs_live(pb)), 1)
        self.assertEqual(pb.memory[P + 4], 10 - BOMB_MP_COST)
        pb.stop()

    def test_one_mp_cannot_throw(self):
        pb = scene(CLASS_PICSEAN)
        arm_mp(pb, 1, 10)
        fire_right(pb)
        self.assertEqual(len(bombs_live(pb)), 0)
        self.assertEqual(pb.memory[P + 4], 1)
        self.assertEqual(pb.memory[P + 19], 0)
        pb.stop()

    def test_exactly_two_mp_throws_and_empties(self):
        pb = scene(CLASS_SAURAN)
        arm_mp(pb, 2, 3)
        fire_right(pb)
        self.assertEqual(len(bombs_live(pb)), 1)
        self.assertEqual(pb.memory[P + 4], 0)
        pb.stop()

    def test_zero_mp_cannot_throw(self):
        pb = scene(CLASS_SAURAN)
        arm_mp(pb, 0, 3)
        fire_right(pb)
        self.assertEqual(len(bombs_live(pb)), 0)
        self.assertEqual(pb.memory[P + 4], 0)
        pb.stop()

    def test_limitless_throws_at_zero_and_one_without_spending(self):
        pb = scene(CLASS_PICSEAN)
        pu_id = addr("_powerup_id")
        try:
            pu_ticks = addr("_powerup_ticks")
        except RuntimeError:
            pu_ticks = None
        pb.memory[pu_id] = LIMITLESS
        if pu_ticks is not None:
            pb.memory[pu_ticks] = 200
        arm_mp(pb, 0, 10)
        fire_right(pb)
        self.assertEqual(len(bombs_live(pb)), 1)
        self.assertEqual(pb.memory[P + 4], 0)
        # Let the fuse die and the 72-frame charge finish, then throw at 1 MP.
        for _ in range(80):
            pb.tick(1)
            if pu_ticks is not None:
                pb.memory[pu_ticks] = 200
            pb.memory[pu_id] = LIMITLESS
        arm_mp(pb, 1, 10)
        fire_right(pb)
        self.assertEqual(len(bombs_live(pb)), 1)
        self.assertEqual(pb.memory[P + 4], 1)
        pb.stop()

    def test_picsean_spam_cannot_hold_the_old_cap(self):
        """Cost 2 must empty a fresh Picsean bar well before the old 41s mark
        and keep bombs-per-minute well under the 72-frame cap of 50."""
        pb = scene(CLASS_PICSEAN)
        arm_mp(pb, 10, 10)
        frames = 60 * 20  # 20s
        thrown = 0
        first_starve = None
        prev_live = 0
        f = 0
        while f < frames:
            pb.memory[P + 24] = ITEM_BOMBS
            pb.memory[P + 18] = ITEM_BOMBS
            if pb.memory[P + 2] < 10:
                pb.memory[P + 2] = 20
                pb.memory[P + 15] = 200
            charge = pb.memory[P + 19]
            mp = pb.memory[P + 4]
            if charge == 0 and mp >= BOMB_MP_COST:
                fire_right(pb)
                f += 3
            else:
                if first_starve is None and mp < BOMB_MP_COST:
                    first_starve = f
                pb.tick(1)
                f += 1
            live = len(bombs_live(pb))
            if live > prev_live:
                thrown += live - prev_live
            prev_live = live
        bpm = thrown / (frames / 60.0 / 60.0)
        self.assertIsNotNone(first_starve, "Picsean never ran out of MP")
        self.assertLess(first_starve / 60.0, 20.0)
        self.assertLess(bpm, 40.0)
        self.assertGreaterEqual(thrown, 5)
        pb.stop()


if __name__ == "__main__":
    unittest.main()
