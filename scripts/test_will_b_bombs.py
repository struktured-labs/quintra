#!/usr/bin/env python3
"""Will-scaled fuse bombs: radius, fragments, and max-tier spend."""
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if (ROOT / "scripts").is_dir():
    sys.path.insert(0, str(ROOT / "scripts"))
else:
    sys.path.insert(0, str(ROOT))

from test_will_max import (  # noqa: E402
    PLAYER as P, ENTITIES as E, TILEMAP as T,
    WILL_OFFSET, LEVEL_OFFSET,
    boot, clear_arena, put16, addr,
)
from test_will_b_weapons import set_will, fire_b  # noqa: E402

ITEM_BOMBS = 48
AUX_BOMB = 0xF7
AUX_SPLASH = 0xF2
ENTITY_SIZE = 28
BGT_CRYSTAL = 22
SPR_BOMB_WAVE = 188
SPR_BOMB_WAVE_H = 189
SPR_BOMB_WAVE_CORNER = 190
SPR_BOMB_FRAG = 191
SPR_BOMB_WAVES = (SPR_BOMB_WAVE, SPR_BOMB_WAVE_H, SPR_BOMB_WAVE_CORNER)
# (level, charge, waygear). waygear=7 raises WILL_LEVEL_CAP to 4 so
# will_level=1 is mid-tier, not already max.
WILL = {
    0: (0, 0, 0),
    1: (0, 45, 0),
    2: (1, 0, 7),
    3: (1, 90, 0),
}


def scene():
    pb = boot(0)
    clear_arena(pb)
    pb.memory[addr("_entity_enemy_count")] = 0
    pb.memory[P + 24] = ITEM_BOMBS
    pb.memory[P + 18] = ITEM_BOMBS
    pb.memory[P + 19] = 0
    pb.memory[P + 13] = 1
    put16(pb, P + 9, 64)
    put16(pb, P + 11, 72)
    pb.memory[P + 1] = 20
    pb.memory[P + 2] = 20
    pb.memory[P + 3] = 16
    pb.memory[P + 4] = 16
    pb.memory[P + 15] = 200  # iframes so a dropped bomb does not kill the hero
    pb.tick(2)
    return pb


def live(pb, aux=None, tile=None):
    out = []
    tiles = None
    if tile is not None:
        tiles = tile if isinstance(tile, (tuple, list, set)) else (tile,)
    for i in range(32):
        base = E + i * ENTITY_SIZE
        if pb.memory[base] == 0 or not (pb.memory[base + 1] & 1):
            continue
        if aux is not None and pb.memory[base + 23] != aux:
            continue
        if tiles is not None and pb.memory[base + 12] not in tiles:
            continue
        out.append(base)
    return out


def plant_crystals(pb):
    """Sparse rings around the explode tile (9,10) = player (64,72) + 4 + 8.
    Twelve crystals, four per Chebyshev ring, so radius is visible without
    asking breakable_set_tile to wait 49 vblanks in one update."""
    # explode at (player.x+4)+4, (player.y+4)+4 -> (72, 80) -> tile (9, 10)
    # r=2/r=3 use diagonals so mid-tier cardinal splashes (15x15 at 16px)
    # cannot pretouch the outer ring.
    spots = [
        # r = 1 cardinals
        (9, 9), (10, 10), (9, 11), (8, 10),
        # r = 2 diagonals
        (7, 8), (11, 8), (7, 12), (11, 12),
        # r = 3 diagonals
        (6, 7), (12, 7), (6, 13), (12, 13),
    ]
    for tx, ty in spots:
        pb.memory[T + ty * 20 + tx] = BGT_CRYSTAL
    return spots


def crystals_left(pb):
    n = 0
    for i in range(20 * 17):
        if pb.memory[T + i] == BGT_CRYSTAL:
            n += 1
    return n


def throw_and_wait_blast(pb, level, charge, waygear=0, frames=80):
    set_will(pb, level, charge, waygear)
    pb.memory[P + 19] = 0
    pb.memory[P + 4] = max(pb.memory[P + 4], 2)
    fire_b(pb)
    peak_splash = 0
    peak_frag = 0
    peak_wave = 0
    saw_bomb = False
    for _ in range(frames):
        if live(pb, aux=AUX_BOMB):
            saw_bomb = True
        peak_splash = max(peak_splash, len(live(pb, aux=AUX_SPLASH)))
        peak_frag = max(peak_frag, len(live(pb, tile=SPR_BOMB_FRAG)))
        peak_wave = max(peak_wave, len(live(pb, tile=SPR_BOMB_WAVES)))
        pb.tick(1)
    return {
        "saw_bomb": saw_bomb,
        "splash": peak_splash,
        "frags": peak_frag,
        "waves": peak_wave,
    }


class TestWillBBombs(unittest.TestCase):
    def test_blast_grows_with_will_tier(self):
        broke = []
        splashes = []
        frags = []
        waves = []
        for tier, (level, charge, way) in WILL.items():
            pb = scene()
            try:
                total = len(plant_crystals(pb))
                pb.tick(2)
                rec = throw_and_wait_blast(pb, level, charge, way)
                gone = total - crystals_left(pb)
                broke.append(gone)
                splashes.append(rec["splash"])
                frags.append(rec["frags"])
                waves.append(rec["waves"])
                self.assertTrue(rec["saw_bomb"], f"tier {tier} never spawned a bomb")
            finally:
                pb.stop(save=False)
        print(
            f"[bomb will] crystals broken {broke}  splash {splashes}  "
            f"frags {frags}  waves {waves}",
            flush=True,
        )
        # Sparse rings: 4 at r=1, 4 at r=2, 4 at r=3. Tile radius is 1,1,2,3.
        print(f"[bomb will] expected rings 4, 4, 8, 12; got {broke}", flush=True)
        self.assertEqual(broke[0], 4)
        self.assertEqual(broke[1], 4)
        self.assertEqual(broke[2], 8)
        self.assertEqual(broke[3], 12)
        self.assertEqual(splashes[0], 1)
        self.assertGreaterEqual(splashes[1], 4)
        self.assertGreaterEqual(splashes[3], splashes[1])
        self.assertEqual(waves[0], 0)
        self.assertGreaterEqual(waves[1], 7)
        self.assertGreaterEqual(waves[3], 7)
        self.assertEqual(frags[0], 0)
        self.assertEqual(frags[1], 0)
        self.assertGreaterEqual(frags[2], 3)
        self.assertGreater(frags[3], frags[2])

    def test_wave_and_frag_oam_keep_s_bank(self):
        """S_BANK (OAM bit 3) must reach shadow OAM so bank-1 tiles draw."""
        pb = scene()
        try:
            set_will(pb, 1, 0, 7)
            pb.memory[P + 4] = 16
            fire_b(pb)
            shadow = 0xC000
            found = 0
            banked = 0
            for _ in range(90):
                for i in range(40):
                    y = pb.memory[shadow + i * 4]
                    tile = pb.memory[shadow + i * 4 + 2]
                    prop = pb.memory[shadow + i * 4 + 3]
                    if not (0 < y < 168):
                        continue
                    if tile in SPR_BOMB_WAVES or tile == SPR_BOMB_FRAG:
                        found += 1
                        if prop & 0x08:
                            banked += 1
                if found:
                    break
                pb.tick(1)
            print(f"[bomb oam] visible={found} s_bank={banked}", flush=True)
            self.assertGreaterEqual(found, 8, "wave/frag sprites never reached shadow OAM")
            self.assertEqual(banked, found, "S_BANK missing on some wave/frag OAM entries")
        finally:
            pb.stop(save=False)

    def test_max_tier_spends_will_and_second_throw_is_not_max(self):
        pb = scene()
        try:
            set_will(pb, 1, 90, 0)
            pb.memory[P + 4] = 16
            fire_b(pb)
            self.assertEqual(pb.memory[P + LEVEL_OFFSET], 0, "max bomb did not reset will_level")
            # fire_b ticks twice; will_charge_tick may add 1 after the spend.
            self.assertLessEqual(pb.memory[P + WILL_OFFSET], 1, "max bomb did not reset will_charge")
            for _ in range(90):
                pb.tick(1)
            self.assertEqual(pb.memory[P + LEVEL_OFFSET], 0)
            pb.memory[P + 4] = 16
            fire_b(pb)
            second_frags = 0
            second_waves = 0
            for _ in range(80):
                second_frags = max(second_frags, len(live(pb, tile=SPR_BOMB_FRAG)))
                second_waves = max(second_waves, len(live(pb, tile=SPR_BOMB_WAVES)))
                pb.tick(1)
            print(
                f"[bomb max-reset] second frags={second_frags} waves={second_waves} "
                f"will={pb.memory[P + LEVEL_OFFSET]},{pb.memory[P + WILL_OFFSET]}",
                flush=True,
            )
            # Mid/max bombs spawn fragments; a spent gauge must not.
            # Waves can appear if will_charge_tick crosses WILL_MAX/3 during
            # the 72-frame item cooldown, which is ordinary regen, not a
            # leftover max blast.
            self.assertEqual(second_frags, 0, "second bomb still spawned mid/max fragments")
            # The cap-1 gauge refills from zero by ordinary regen in about
            # 170 frames, so the level may bank back by one at the very end,
            # depending on frame phase. More than one would be a leftover max.
            self.assertLessEqual(pb.memory[P + LEVEL_OFFSET], 1)
        finally:
            pb.stop(save=False)


if __name__ == "__main__":
    unittest.main()
