#!/usr/bin/env python3
"""ROM contract: sanctuaries plus a real connected three-screen village."""
import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import (
    STAGE_BOSS_ROOM, STAGE_START, VILLAGE_ROOM, dungeon_direction,
)

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    m = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not m:
        raise RuntimeError(f"missing symbol {name}")
    return int(m.group(1), 16)


def main():
    rs, pl, en, screen, tilemap = map(addr, (
        "_run_state", "_player", "_entities", "_loop_current_screen",
        "_room_tilemap"))
    pb = PyBoy(str(ROM), window="null", cgb=True)

    def tick(n):
        for _ in range(n):
            pb.tick()

    def entities(kind=None):
        out = []
        for i in range(32):
            ep = en + i * 28
            if pb.memory[ep] != 3:
                continue
            if kind is None or pb.memory[ep + 17] == kind:
                out.append(ep)
        return out

    def entities_by_type(entity_type):
        return [en + i * 28 for i in range(32)
                if pb.memory[en + i * 28] == entity_type]

    def clear_hostiles():
        for i in range(32):
            ep = en + i * 28
            if pb.memory[ep] == 2:
                pb.memory[ep] = pb.memory[ep + 1] = 0

    def enter_from_previous(target):
        clear_hostiles()
        if target in VILLAGE_ROOM.values():
            after_stage = next(stage for stage, room in VILLAGE_ROOM.items()
                               if room == target)
            pb.memory[rs + 1] = STAGE_BOSS_ROOM[after_stage - 1]
            pb.memory[rs + 11] = after_stage
            pb.memory[rs + 17] = 1
            pb.memory[rs + 18] = 6
            pb.memory[rs + 19] = 0
            pb.memory[tilemap + 8 * 20 + 10] = 34
            x, y = 72, 52
        else:
            stage = next(i for i, boss in enumerate(STAGE_BOSS_ROOM)
                         if target == boss - 1)
            source_local = target - 1 - STAGE_START[stage]
            target_local = target - STAGE_START[stage]
            direction = dungeon_direction(source_local, target_local)
            pb.memory[rs + 1] = target - 1
            pb.memory[rs + 11] = stage
            x, y = {
                0: (72, 0), 1: (144, 60),
                2: (72, 120), 3: (0, 60),
            }[direction]
            for tx, ty in {
                0: ((9, 0), (10, 0)), 1: ((19, 8), (19, 9)),
                2: ((9, 16), (10, 16)), 3: ((0, 8), (0, 9)),
            }[direction]:
                pb.memory[tilemap + ty * 20 + tx] = 3
        for off, value in ((9, x), (10, 0), (11, y), (12, 0)):
            pb.memory[pl + off] = value
        tick(45)
        assert pb.memory[rs + 1] == target, f"could not enter room {target}"

    def leave(direction):
        positions = {
            "north": (72, 0), "east": (144, 60),
            "south": (72, 120), "west": (0, 60),
        }
        x, y = positions[direction]
        for off, value in ((9, x), (10, 0), (11, y), (12, 0)):
            pb.memory[pl + off] = value
        tick(45)

    tick(240)
    pb.button("start"); tick(30)
    pb.button("down"); tick(8)  # Sauran
    pb.button("a"); tick(60)
    assert pb.memory[screen] == 5 and pb.memory[pl] == 1

    # Every pre-boss sanctuary remains a guaranteed full reset.
    pb.memory[pl + 2] = 1
    pb.memory[pl + 4] = 0
    enter_from_previous(STAGE_BOSS_ROOM[0] - 1)
    assert pb.memory[pl + 2] == pb.memory[pl + 1]
    assert pb.memory[pl + 4] == pb.memory[pl + 3]

    # Screen 0: named arrival square, elder/fountain, chartwright, a paid
    # full-route chart, Lorekeeper, Bellkeeper, and three authored exits. The two route-
    # reading choices make villages useful between procgen dungeons rather
    # than scenery, while the fourth resident makes the civic space feel
    # inhabited without changing the economy.
    town_room = VILLAGE_ROOM[3]
    next_room = STAGE_START[3]
    enter_from_previous(town_room)
    assert pb.memory[rs + 19] == 0, "town did not begin in arrival square"
    elder = entities(7)
    chartwright = entities(12)
    waykeeper = entities(15)
    lorekeeper = entities(17)
    bellkeeper = entities(18)
    assert len(elder) == 1 and pb.memory[elder[0] + 12] == 69
    assert len(chartwright) == 1 and pb.memory[chartwright[0] + 12] == 123
    assert len(waykeeper) == 1 and pb.memory[waykeeper[0] + 12] == 124, \
        "arrival square lacks its dedicated north-gate Waykeeper"
    assert len(lorekeeper) == 1 and pb.memory[lorekeeper[0] + 12] == 126, \
        "arrival square lacks its dedicated scroll-bearing Lorekeeper"
    assert len(bellkeeper) == 1 and pb.memory[bellkeeper[0] + 12] == 79, \
        "arrival square lacks its dedicated Bellkeeper landmark"
    # The Waykeeper safely borrows the Rune Lantern's 8x8 VRAM slot only in a
    # town. Keep the exact town bytes so the transition below proves a normal
    # dungeon entry restores combat art rather than merely despawning the NPC.
    pb.memory[0xFF4F] = 0
    waykeeper_tile = bytes(pb.memory[0x8000 + 124 * 16:0x8000 + 125 * 16])
    assert waykeeper_tile == bytes((
        0x18, 0x18, 0x3C, 0x24, 0x5A, 0x66, 0x5A, 0x7E,
        0x3C, 0x7E, 0x24, 0x3C, 0x24, 0x3C, 0x42, 0x42,
    )), f"town arrival did not load Waykeeper art: {waykeeper_tile.hex()}"
    bellkeeper_tile = bytes(pb.memory[0x8000 + 79 * 16:0x8000 + 80 * 16])
    assert bellkeeper_tile == bytes((
        0x18, 0x18, 0x3C, 0x24, 0x5A, 0x66, 0x3C, 0x7E,
        0x18, 0x7E, 0x3C, 0x7E, 0x24, 0x7E, 0x3C, 0x3C,
    )), f"town arrival did not load Bellkeeper art: {bellkeeper_tile.hex()}"
    lorekeeper_tile = bytes(pb.memory[0x8000 + 126 * 16:0x8000 + 127 * 16])
    assert lorekeeper_tile == bytes((
        0x10, 0x10, 0x38, 0x28, 0x7C, 0x44, 0x5A, 0x66,
        0x3C, 0x7E, 0x2C, 0x3C, 0x52, 0x52, 0x42, 0x42,
    )), f"town arrival did not load Lorekeeper art into the Surge-orb slot: {lorekeeper_tile.hex()}"
    lore_callout_tile = bytes(pb.memory[0x8000 + 125 * 16:0x8000 + 126 * 16])
    assert lore_callout_tile == bytes((
        0x3C, 0x00, 0x7E, 0x18, 0xC3, 0x24, 0xBD, 0x42,
        0xBD, 0x42, 0xC3, 0x24, 0x7E, 0x18, 0x3C, 0x00,
    )), "town arrival did not load the Lorekeeper's scroll cue"
    arrival_wares = entities(4)
    assert len(arrival_wares) == 1 and pb.memory[arrival_wares[0] + 18] == 7, \
        "arrival square lacks its dedicated Cartographer's Chart"
    chart_ware = arrival_wares[0]
    assert pb.memory[chart_ware + 12] == 35 and pb.memory[chart_ware + 13] == 6
    assert pb.memory[chart_ware + 19] == 15, "Cartographer's Chart price drifted"
    arrival = bytes(pb.memory[addr("_room_tilemap"):addr("_room_tilemap") + 340])
    arrival_gate_cells = (9, 10, 8 * 20, 8 * 20 + 19, 9 * 20, 9 * 20 + 19)
    assert all(arrival[cell] == 3 for cell in arrival_gate_cells), \
        "arrival square does not expose its N/E/W village gates"
    assert arrival[16 * 20 + 9] != 3 and arrival[16 * 20 + 10] != 3, \
        "arrival square unexpectedly gained a south gate"
    # The arrival screen must visually read as a settlement, not just a
    # grass clearing with NPCs. Its two small rooflines frame the fountain;
    # doorstep paths keep the civic routes open around both buildings.
    assert arrival.count(37) == 16, "arrival square lost its paired house roofs"
    assert arrival[3 * 20 + 2] == arrival[4 * 20 + 5] == 37
    assert arrival[12 * 20 + 14] == arrival[13 * 20 + 17] == 37
    assert arrival[6 * 20 + 3] == arrival[11 * 20 + 16] == 36, \
        "arrival square lost its house-to-fountain doorstep paths"
    pb.memory[0xFF4F] = 0
    assert bytes(pb.memory[0x9800 + 1 * 32 + 7:0x9800 + 1 * 32 + 14]) == \
        bytes((83, 77, 81, 81, 84, 85, 86)), \
        "arrival square lacks its VILLAGE playfield landmark"
    pb.screen.image.save(ROOT / "tmp" / "town-arrival.png")

    # The Lorekeeper's distinct open-scroll cue appears nearby. This is a
    # readable lore invitation, not a purchase or a hidden stat interaction.
    lx, ly = pb.memory[lorekeeper[0] + 3], (pb.memory[lorekeeper[0] + 7] - 8) & 0xFF
    for off, value in ((9, lx), (10, 0), (11, ly - 24), (12, 0)):
        pb.memory[pl + off] = value
    tick(4)
    assert any(pb.memory[fx + 12] == 125 and pb.memory[fx + 13] == 6
               for fx in entities_by_type(4)), \
        "nearby Lorekeeper did not show its distinct scroll cue"

    # SELECT stays a graphical compass in a village too. The old text-only
    # town report made a three-screen settlement read like one strange room;
    # this tile graph exposes its craft quarter, arrival square, market, and
    # onward north gate at a glance.
    pb.button("select"); tick(120)
    assert pb.memory[screen] == 8, "SELECT did not open town compass"
    pb.memory[0xFF4F] = 0
    bg = 0x9800
    assert pb.memory[bg + 9 * 32 + 9] == 33, \
        f"arrival square lacks current marker (got {pb.memory[bg + 9 * 32 + 9]})"
    assert pb.memory[bg + 9 * 32 + 3] == 37, "craft quarter lacks roof marker"
    assert pb.memory[bg + 9 * 32 + 15] == 22, "market lacks crystal marker"
    assert pb.memory[bg + 4 * 32 + 9] == 3, "town compass lacks north gate"
    pb.screen.image.save(ROOT / "tmp" / "town-tile-map.png")
    pb.button("b"); tick(30)
    assert pb.memory[screen] == 5, "town compass did not resume arrival square"

    # Elder is a visible, permanent full blessing.
    # The real Riftwild gate arrives near the fountain and can legitimately
    # trigger the one-per-visit blessing before this synthetic interaction.
    # Re-arm only the resident's contact latch; HP/MP changes below still flow
    # through the cartridge collision path under test.
    pb.memory[elder[0] + 15] = 0
    pb.memory[pl + 2] = 1
    pb.memory[pl + 4] = 0
    ex, ey = pb.memory[elder[0] + 3], (pb.memory[elder[0] + 7] - 8) & 0xFF
    for off, value in ((9, ex), (10, 0), (11, ey), (12, 0)):
        pb.memory[pl + off] = value
    tick(5)
    assert pb.memory[pl + 2] == pb.memory[pl + 1]
    assert pb.memory[pl + 4] == pb.memory[pl + 3]
    assert pb.memory[elder[0]] == 3

    # The Chartwright scouts the first two rooms of the next route without
    # turning the procedural map into a fully revealed spoiler. Route
    # knowledge survives the north gate separately from the town compass.
    pb.memory[rs + 25] = 0
    ex, ey = pb.memory[chartwright[0] + 3], (pb.memory[chartwright[0] + 7] - 8) & 0xFF
    for off, value in ((9, ex), (10, 0), (11, ey), (12, 0)):
        pb.memory[pl + off] = value
    tick(5)
    assert pb.memory[rs + 25] == 0x03, "Chartwright did not scout two route rooms"
    assert pb.memory[chartwright[0] + 15] == 1, "Chartwright blessing did not latch"
    # The paid chart is a stronger, clearly signposted town service. Its map
    # glyph and price must appear before contact; buying it through ordinary
    # collision upgrades the stored two-room scout to the full 6x5 route.
    cx, cy = pb.memory[chart_ware + 3], (pb.memory[chart_ware + 7] - 8) & 0xFF
    for off, value in ((9, cx), (10, 0), (11, cy - 24), (12, 0)):
        pb.memory[pl + off] = value
    tick(6)
    pb.memory[0xFF4F] = 0
    assert pb.memory[0x9C00 + 12] == 47, \
        f"nearby Chart lacks route-map offer glyph (got {pb.memory[0x9C00 + 12]})"
    assert bytes(pb.memory[0x9C00 + 13:0x9C00 + 16]) == bytes((7, 10, 14)), \
        "nearby Chart did not show its $15 price"
    pb.memory[pl + 16], pb.memory[pl + 17] = 15, 0
    for off, value in ((9, cx), (10, 0), (11, cy), (12, 0)):
        pb.memory[pl + off] = value
    tick(6)
    assert pb.memory[chart_ware] == 0, "Cartographer's Chart could not be purchased"
    assert (pb.memory[rs + 25] == 0xFF
            and pb.memory[rs + 30] == 0xFF
            and pb.memory[rs + 32] == 0xFF
            and pb.memory[rs + 34] == 0x3F), \
        "paid Chart did not reveal the full thirty-cell route"

    # East branch: dedicated market with merchant and four visually distinct
    # wares. Stock must retain its own heart/relic art rather than collapsing
    # into the old ambiguous orange tag sprite.
    leave("east")
    assert pb.memory[rs + 1] == town_room and pb.memory[rs + 19] == 1
    merchant, wares, tags = entities(8), entities(4), entities(13)
    assert len(merchant) == 1 and pb.memory[merchant[0] + 12] == 70
    assert len(wares) == 4
    assert len(tags) == 4 and all(pb.memory[t + 12] == 81 for t in tags), \
        "market stock lacks persistent gold sale markers"
    assert {pb.memory[t + 18] for t in tags} == {
        (w - en) // 28 for w in wares
    }, "sale markers are not bound to their wares"
    assert {pb.memory[w + 18] for w in wares} == {0, 2, 5, 8}
    tick(70)
    assert pb.memory[wares[0] + 12] == 30, "heart stock lost its heart art"
    assert all(pb.memory[w + 12] == 35 for w in wares
               if pb.memory[w + 18] in {2, 8}), \
        "relic stock lost its orb art"
    surge = next(w for w in wares if pb.memory[w + 18] == 5)
    weapon = next(w for w in wares if pb.memory[w + 18] == 8)
    assert pb.memory[surge + 12] == 126 and pb.memory[surge + 13] == 6, \
        "market lacks its cyan Surge Tonic shelf"
    assert pb.memory[weapon + 12] == 35 and pb.memory[weapon + 13] == 4, \
        "market weapon trade lacks its distinct red weapon-orb art"
    assert pb.memory[weapon + 19] == 30, "market weapon trade price drifted"
    assert pb.memory[weapon + 20] in {20, 21}, \
        "market weapon trade did not stock a special flail/spear index"
    pb.memory[0xFF4F] = 0
    assert bytes(pb.memory[0x9800 + 1 * 32 + 7:0x9800 + 1 * 32 + 13]) == \
        bytes((87, 84, 76, 88, 86, 79)), \
        "east quarter lacks its MARKET playfield landmark"
    # A nearby merchant speaks visually before the player risks walking into
    # stock: a coin speech bubble makes the NPC's purpose legible even on a
    # busy market screen.
    mx, my = pb.memory[merchant[0] + 3], (pb.memory[merchant[0] + 7] - 8) & 0xFF
    for off, value in ((9, mx), (10, 0), (11, my + 24), (12, 0)):
        pb.memory[pl + off] = value
    tick(3)
    assert any(pb.memory[fx + 12] == 125 for fx in entities_by_type(4)), \
        "nearby merchant did not show its trade callout"
    # Approach a ware without touching it: the market announces its price
    # before a walk-into purchase. Leaving the stall clears the context hint.
    ware = wares[0]
    pb.memory[pl + 16] = pb.memory[pl + 17] = 0
    wx, wy = pb.memory[ware + 3], (pb.memory[ware + 7] - 8) & 0xFF
    # The lower shelf sits below the market's roof line. Stand one tile above
    # its feet-anchor: close enough for the HUD context, but not a purchase.
    for off, value in ((9, wx), (10, 0), (11, wy - 8), (12, 0)):
        pb.memory[pl + off] = value
    tick(6)
    pb.memory[0xFF4F] = 0
    assert pb.memory[0x9C00 + 12] == 40, \
        "nearby heart stock did not show the healing offer icon"
    assert bytes(pb.memory[0x9C00 + 13:0x9C00 + 16]) == bytes((7, 8, 14)), \
        "nearby heart stock did not show its $5 price beside the offer icon"
    for off, value in ((9, 16), (10, 0), (11, 16), (12, 0)):
        pb.memory[pl + off] = value
    tick(6)
    pb.memory[0xFF4F] = 0
    assert pb.memory[0x9C00 + 12] == 8, "market price HUD stayed after leaving stall"

    # The dedicated tonic has its own cyan stock sprite and lightning offer
    # glyph, so it reads as a temporary weapon burst rather than a mystery orb.
    sx, sy = pb.memory[surge + 3], (pb.memory[surge + 7] - 8) & 0xFF
    for off, value in ((9, sx), (10, 0), (11, sy - 24), (12, 0)):
        pb.memory[pl + off] = value
    tick(6)
    pb.memory[0xFF4F] = 0
    assert pb.memory[0x9C00 + 12] == 45, "nearby Surge Tonic lacks lightning offer icon"
    assert bytes(pb.memory[0x9C00 + 13:0x9C00 + 16]) == bytes((7, 11, 9)), \
        "nearby Surge Tonic did not show its $20 price"
    # The far shelf must be a real reachable purchase, not a decorative
    # fourth icon against the border. Buy it through the ordinary walk-into
    # interaction; the generic Surge contract covers its timed combat effect.
    pb.memory[pl + 16], pb.memory[pl + 17] = 20, 0
    for off, value in ((9, sx), (10, 0), (11, sy), (12, 0)):
        pb.memory[pl + off] = value
    tick(6)
    assert pb.memory[surge] == 0, "far market Surge Tonic could not be purchased"
    assert len(entities(13)) == 3, "Surge sale marker remained after purchase"

    # Touch one unaffordable offer: it survives and latches one reject buzz.
    for off, value in ((9, wx), (10, 0), (11, wy), (12, 0)):
        pb.memory[pl + off] = value
    tick(6)
    assert pb.memory[ware] == 3 and pb.memory[ware + 21] == 1
    pb.memory[0xFF4F] = 0
    assert pb.memory[0x9C00 + 12] == 40, \
        "market contact did not preserve the healing offer icon"
    pb.screen.image.save(ROOT / "tmp" / "town-market.png")

    # A sold ware removes its own marker. Restore currency only for this
    # contract check; the purchase itself remains the game's normal walk-into
    # interaction, with no UI-only shortcut.
    pb.memory[pl + 16] = 99
    pb.memory[pl + 17] = 0
    tick(6)
    assert pb.memory[ware] == 0, "purchased market ware remained active"
    tick(2)
    assert len(entities(13)) == 2, "sale marker remained after its ware sold"

    # The market's central shelf is a paid A-weapon trade, not a random stat
    # orb. Its dedicated HUD blade glyph and ordinary collision transaction
    # must expose a seed-stable special weapon and never drop the old weapon
    # back onto the counter for a free re-swap.
    old_weapon = pb.memory[pl + 21]
    advertised_weapon = pb.memory[weapon + 20]
    wx, wy = pb.memory[weapon + 3], (pb.memory[weapon + 7] - 8) & 0xFF
    for off, value in ((9, wx), (10, 0), (11, wy - 8), (12, 0)):
        pb.memory[pl + off] = value
    tick(6)
    pb.memory[0xFF4F] = 0
    assert pb.memory[0x9C00 + 12] == 48, \
        "nearby market weapon trade lacks its blade offer glyph"
    assert bytes(pb.memory[0x9C00 + 13:0x9C00 + 16]) == bytes((7, 12, 9)), \
        "nearby market weapon trade did not show its $30 price"
    pb.memory[pl + 16], pb.memory[pl + 17] = 30, 0
    for off, value in ((9, wx), (10, 0), (11, wy), (12, 0)):
        pb.memory[pl + off] = value
    tick(6)
    assert pb.memory[weapon] == 0 and pb.memory[pl + 21] == advertised_weapon \
        and advertised_weapon != old_weapon, "market weapon trade did not replace A weapon"
    assert not entities(5), "market weapon trade dropped an old weapon for free"
    assert len(entities(13)) == 1, "weapon sale marker remained after trade"

    # West back to arrival, then west again: forge/apothecary quarter.
    leave("west")
    assert pb.memory[rs + 19] == 0
    leave("west")
    assert pb.memory[rs + 1] == town_room and pb.memory[rs + 19] == 2
    smith, apothecary, wares = entities(9), entities(10), entities(4)
    assert len(smith) == len(apothecary) == 1
    assert pb.memory[smith[0] + 12] == 71
    assert pb.memory[apothecary[0] + 12] == 79
    # Arrival borrows slot 79 for the Bellkeeper. The craft quarter must
    # reload the real apothecary art after two lateral town transitions;
    # checking only the shared tile number would miss a visual identity leak.
    apothecary_tile = bytes(pb.memory[0x8000 + 79 * 16:0x8000 + 80 * 16])
    assert apothecary_tile == bytes((
        0x18, 0x00, 0x3C, 0x18, 0x66, 0x3C, 0x7E, 0x24,
        0x24, 0x18, 0x7E, 0x18, 0x66, 0x24, 0x24, 0x00,
    )), "craft-quarter apothecary inherited Bellkeeper art"
    assert len(wares) == 3 and {pb.memory[w + 18] for w in wares} == {3, 4, 6}
    pb.memory[0xFF4F] = 0
    assert bytes(pb.memory[0x9800 + 1 * 32 + 8:0x9800 + 1 * 32 + 13]) == \
        bytes((78, 89, 76, 85, 86)), \
        "west quarter lacks its FORGE playfield landmark"
    assert len({69, 70, pb.memory[smith[0] + 12], pb.memory[apothecary[0] + 12]}) == 4
    # The apothecary's crimson shelf makes the fifth-kill Vampiric Sigil an
    # intentional run-long sustain purchase instead of a barely-seen random
    # drop. Check the semantic fangs HUD before buying through normal contact.
    vamp = next(w for w in wares if pb.memory[w + 18] == 6)
    assert pb.memory[vamp + 12] == 35 and pb.memory[vamp + 13] == 4
    assert pb.memory[vamp + 19] == 35, "Vampiric Sigil price drifted"
    vx, vy = pb.memory[vamp + 3], (pb.memory[vamp + 7] - 8) & 0xFF
    for off, value in ((9, vx), (10, 0), (11, vy - 24), (12, 0)):
        pb.memory[pl + off] = value
    tick(6)
    pb.memory[0xFF4F] = 0
    assert pb.memory[0x9C00 + 12] == 46, \
        "nearby Vampiric Sigil lacks the fangs offer glyph"
    assert bytes(pb.memory[0x9C00 + 13:0x9C00 + 16]) == bytes((7, 12, 14)), \
        "nearby Vampiric Sigil did not show its $35 price"
    old_hp_max, old_atk = pb.memory[pl + 1], pb.memory[pl + 5]
    pb.memory[pl + 16], pb.memory[pl + 17] = 99, 0
    for off, value in ((9, vx), (10, 0), (11, vy), (12, 0)):
        pb.memory[pl + off] = value
    tick(6)
    assert pb.memory[vamp] == 0, "Vampiric Sigil shelf could not be purchased"
    assert (pb.memory[pl + 1] == min(16, old_hp_max + 1)
            and pb.memory[pl + 5] == old_atk + 1), \
        ("Vampiric Sigil did not apply its permanent health/attack build effects "
         f"(hp_max {old_hp_max}->{pb.memory[pl + 1]}, atk {old_atk}->{pb.memory[pl + 5]})")
    pb.screen.image.save(ROOT / "tmp" / "town-quarter.png")

    # Return to arrival and leave north: only now does dungeon depth advance.
    leave("east")
    assert pb.memory[rs + 19] == 0 and pb.memory[rs + 1] == town_room
    leave("north")
    assert pb.memory[rs + 1] == next_room, \
        "north village gate did not continue the run"
    assert pb.memory[rs + 19] == 0, "town-local screen leaked into dungeon state"
    assert (pb.memory[rs + 20] == 0xFF
            and pb.memory[rs + 29] == 0xFF
            and pb.memory[rs + 31] == 0xFF
            and pb.memory[rs + 33] == 0x3F
            and pb.memory[rs + 25] == 0
            and pb.memory[rs + 30] == 0
            and pb.memory[rs + 32] == 0
            and pb.memory[rs + 34] == 0), \
        f"paid Chart did not become a one-dungeon full compass reveal (seen={pb.memory[rs + 20]:02x}, queued={pb.memory[rs + 25]:02x})"
    pb.stop(save=False)
    print("[town] PASS connected arrival + market + forge quarter + north continuation")


if __name__ == "__main__":
    main()
