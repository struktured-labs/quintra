#!/usr/bin/env python3
"""ROM regression: stage identity changes generated traversal geometry."""
import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import (
    STAGE_START, dungeon_maze_neighbor, dungeon_predecessor, dungeon_size,
    mission_graph,
)
from make_stage_states import (
    boot_to_stage, cross_graph_edge, normalize_compact_source,
    select_rom_topology, symbol_addresses,
)

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
ROOM_W, ROOM_H = 20, 17
BGT_PILLAR, BGT_CRYSTAL, BGT_SPIKES = 21, 22, 31
STAGE_RAIL_X = (2, 3, 16, 17)
HARD_SCENERY = {2, BGT_PILLAR, BGT_CRYSTAL}
FLOOR_SCENERY = {1, 3, 19, 20, 23, BGT_SPIKES, 33, 34}


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


RS, PL, EN, TM = map(addr, ("_run_state", "_player", "_entities", "_room_tilemap"))


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def wait_for_generated_room(pb):
    """Return only after the cartridge has committed and displayed the room."""
    previous = None
    stable = 0
    for _ in range(480):
        pb.tick()
        tiles = bytes(pb.memory[TM + i] for i in range(ROOM_W * ROOM_H))
        lcd_on = bool(pb.memory[0xFF40] & 0x80)
        committed = not any(value & 0x80 for value in tiles)
        stable = stable + 1 if lcd_on and committed and tiles == previous else 0
        previous = tiles
        # A streamed 31x31 transaction can leave the compact western ABI
        # unchanged while its banked off-screen court, role overlays, and
        # suspend commit are still finishing. Ten matching frontend frames
        # was short enough to sample a half-authored Deep district after the
        # denser procgen pass. Require a sustained settled window.
        if stable >= 30:
            return list(tiles)
    raise AssertionError("room generation did not settle within 480 frames")


def archetype_sample_cell(stage, seed, preferred=4):
    """Choose an ordinary wide court with no role/secret terrain overlay."""
    roles = set(mission_graph(dungeon_size(stage), seed, stage)["sequence"])
    for cell in (preferred, 4, 6, 10, 12, 13, 14, 16, 18, 20, 22, 24, 25, 26):
        if cell >= dungeon_size(stage) - 3 or cell in roles or cell == 15:
            continue
        room_seed = (seed ^ (((STAGE_START[stage] + cell) * 0x9E3779B9)
                             & 0xFFFFFFFF)) & 0xFFFFFFFF
        if ((room_seed >> 16) & 31) > 2:
            return cell
    raise AssertionError(f"no ordinary archetype sample stage={stage} seed={seed:#x}")


def generated_room(stage, seed=0xCAFE1234, screenshot=None, probe=None,
                   local_room=None, dungeon_phase=0, pre_cross=None):
    # Enter through the real Riftwild gate, then cross one reciprocal maze
    # edge. BGT_PORTAL is a mission-branch traversal mechanic now (local
    # 2<->8), not a generic test-only "next room" shortcut.
    select_rom_topology(ROM)
    addrs = symbol_addresses(ROM)
    pb, _ram, _entry = boot_to_stage(ROM, addrs, stage, "normal", 0)

    # Mission and hidden-secret roles are seed-first. Choose a normal wide
    # court when callers want stage identity, while explicit role/fixture
    # tests can still request an exact local cell.
    if local_room is None:
        local_room = archetype_sample_cell(stage, seed)
    target = STAGE_START[stage] + local_room
    for i, byte in enumerate(seed.to_bytes(4, "little")):
        pb.memory[RS + 2 + i] = byte
    # Rebuild seed-first stage roles and its two-state dungeon law for the
    # requested sample rather than retaining the boot fixture's seed.
    pb.memory[RS + 36] = 0
    pb.memory[RS + 37] = 0
    pb.memory[RS + 12] = 0
    pb.memory[RS + 13] = 0
    pb.memory[RS + 28] = dungeon_phase
    # The synthetic source replaces the live entry room. Do not carry that
    # room's combat/rune seal into a different graph cell.
    pb.memory[addrs["_room_puzzle_locked"]] = 0
    pb.memory[addr("_room_combat_sealed")] = 0
    source_local, direction_id = dungeon_predecessor(
        local_room, dungeon_size(stage), seed, stage)
    pb.memory[RS + 1] = STAGE_START[stage] + source_local
    pb.memory[RS + 6] = 0xFF
    normalize_compact_source(pb, addrs)
    if pre_cross is not None:
        pre_cross(pb, addrs)
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == 2:
            pb.memory[ep] = pb.memory[ep + 1] = 0
    direction = ("up", "right", "down", "left")[direction_id]
    cross_graph_edge(pb, PL, TM, direction)
    for _ in range(120):
        pb.tick()
        if pb.memory[RS + 1] == target:
            break
    pb.button_release(direction)
    assert pb.memory[RS + 1] == target, (
        f"could not enter stage {stage} room {local_room}; "
        f"source={source_local} dir={direction} now={pb.memory[RS + 1]} "
        f"screen={pb.memory[addr('_loop_current_screen')]} "
        f"player=({pb.memory[PL + 9]}, {pb.memory[PL + 11]})")
    # The real dungeon-entry transaction resets puzzle state just before the
    # counter changes. Select the requested paired-switch state at that
    # observable boundary, before the destination role is prepared.
    pb.memory[RS + 28] = dungeon_phase
    tiles = wait_for_generated_room(pb)
    if screenshot is not None:
        screenshot.parent.mkdir(exist_ok=True)
        pb.screen.image.save(screenshot)
    if probe is not None:
        probe(pb, tiles)
    pb.stop(save=False)
    return tiles


def tile(tiles, x, y):
    return tiles[y * ROOM_W + x]


def assert_no_false_one_tile_gaps(label, tiles):
    """Every visible opening between permanent masses admits the champion.

    A lone 8px floor cell between two pillars/crystals is not a secret or a
    puzzle: the 12px feet box cannot occupy it, yet the former small scenery
    silhouettes made it look like a plausible route. Keep decorative
    compression out of the generated traversal language.
    """
    false_gaps = []
    for y in range(1, ROOM_H - 1):
        for x in range(1, ROOM_W - 1):
            if tile(tiles, x, y) not in FLOOR_SCENERY:
                continue
            if (tile(tiles, x - 1, y) in HARD_SCENERY
                    and tile(tiles, x + 1, y) in HARD_SCENERY):
                false_gaps.append((
                    x, y, "vertical slit",
                    tile(tiles, x - 1, y), tile(tiles, x, y),
                    tile(tiles, x + 1, y),
                ))
            if (tile(tiles, x, y - 1) in HARD_SCENERY
                    and tile(tiles, x, y + 1) in HARD_SCENERY):
                false_gaps.append((
                    x, y, "horizontal slit",
                    tile(tiles, x, y - 1), tile(tiles, x, y),
                    tile(tiles, x, y + 1),
                ))
    assert not false_gaps, (
        f"{label} contains champion-inaccessible visible gaps: "
        f"{false_gaps[:8]}"
    )


def reachable_exits(tiles, start):
    walkable = {1, 3, 7, 19, 20, 23, 31, 33, 34, *range(9, 19)}

    def body_ok(x, y):
        return (1 <= x <= 19 and 1 <= y <= 16
                and all(tile(tiles, tx, ty) in walkable
                        for tx, ty in ((x - 1, y - 1), (x, y - 1),
                                       (x - 1, y), (x, y))))

    seen, todo = {start}, [start]
    while todo:
        x, y = todo.pop()
        for nx, ny in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
            if (nx, ny) not in seen and body_ok(nx, ny):
                seen.add((nx, ny))
                todo.append((nx, ny))
    exits = {(10, 1), (19, 9), (10, 16), (1, 9)}
    return exits & seen


def expected_graph_exits(stage, local_room, seed):
    positions = ((10, 1), (19, 9), (10, 16), (1, 9))
    size = dungeon_size(stage)
    return {
        positions[direction] for direction in range(4)
        if dungeon_maze_neighbor(
            local_room, size, direction, seed, stage
        ) is not None
    }


def assert_graph_exits(label, exits, stage, local_room, seed=0xCAFE1234,
                       *, wide=False):
    expected = expected_graph_exits(stage, local_room, seed)
    wide = wide or local_room in (4, 5, 10, 11, 16, 17, 22, 23)
    if wide:
        # A 248x248 approach/court extends east and south from the legacy
        # 20x17 storage plane. Those two old edge samples are therefore
        # mandatory interior seams, regardless of whether the real graph owns
        # a far east/south door at x=27/y=24.
        expected |= {(19, 9), (10, 16)}
    assert exits == expected, (
        f"{label} authored graph exits disconnected: "
        f"expected={expected} reached={exits}"
    )

def assert_escape_rails(label, tiles):
    hard = {21, 22, 25, 28, 29, 30, 32}
    blocked = [
        (x, y, tile(tiles, x, y))
        for y in range(2, 15) for x in STAGE_RAIL_X
        if tile(tiles, x, y) in hard
    ]
    assert not blocked, (
        f"{label} layered geometry rebuilt a one-way body pocket: {blocked[:4]}"
    )


def main():
    def assert_waypoint_patrol(pb, _tiles):
        enemies = sum(
            pb.memory[EN + i * 28] == 2
            and pb.memory[EN + i * 28 + 1] & 1
            for i in range(32)
        )
        # The crowd pass raised this authored landmark from an exact pair to
        # a light one-to-three patrol. It must still read as a breather beside
        # the 12-18-body scrolling courts, not as an empty or dense fallback.
        assert 1 <= enemies <= 3, (
            f"wing landmark lost its light patrol pacing beat ({enemies})"
        )

    grove = generated_room(1, 2064128938, local_room=4)  # controller-agent seed 1
    assert_no_false_one_tile_gaps("Verdant grove", grove)
    grove_sites = [(4, 4), (5, 4), (14, 4), (15, 4),
                   (4, 12), (5, 12), (14, 12), (15, 12)]
    grove_crystals = sum(tile(grove, x, y) == BGT_CRYSTAL for x, y in grove_sites)
    assert grove_crystals >= 4, f"Verdant grove silhouette missing ({grove_crystals}/8)"
    grove_exits = reachable_exits(grove, (18, 9))
    assert_graph_exits("Verdant grove", grove_exits, 1, 4, 2064128938)
    # Room eleven begins the second long wing. It must repeat the stage's
    # authored identity and use a lighter combat patrol, not fall back to an
    # anonymous dense procgen room.
    grove_wing = generated_room(
        1, 2064128938, local_room=11, probe=assert_waypoint_patrol
    )
    assert_no_false_one_tile_gaps("Verdant second wing", grove_wing)
    # Verdant now owns six asymmetric clearing silhouettes instead of one
    # repeated eight-cell stamp. Require a strong living-growth footprint
    # without forcing its second wing to clone room four's exact corners.
    grove_wing_crystals = sum(value == BGT_CRYSTAL for value in grove_wing)
    assert grove_wing_crystals >= 8, (
        f"Verdant second-wing identity too sparse ({grove_wing_crystals})"
    )
    assert_graph_exits(
        "Verdant second wing",
        reachable_exits(grove_wing, (18, 9)), 1, 11, 2064128938, wide=True
    )

    # Ember is a phase-family dungeon: room 1's compact central switch apron
    # leaves both authored hazard seams intact, whereas room 2 deliberately
    # adds the cross-room phase wall.
    ember = generated_room(2, local_room=1)
    assert_no_false_one_tile_gaps("Ember gauntlet", ember)
    seam_spikes = sum(
        tile(ember, x, y) == BGT_SPIKES
        for x in (5, 14) for y in range(3, 15)
    )
    assert seam_spikes >= 10, f"Ember hazard seams missing ({seam_spikes}/24)"
    # The two three-tile breathing gaps must survive, keeping the hazard a
    # routing choice rather than unavoidable chip damage.
    assert any(tile(ember, 5, y) != BGT_SPIKES for y in range(4, 14))
    assert any(tile(ember, 14, y) != BGT_SPIKES for y in range(4, 14))
    ember_exits = reachable_exits(ember, (18, 9))
    assert_graph_exits("Ember gauntlet", ember_exits, 2, 1)

    # Sample a non-Rift chamber so this contract measures the complete
    # octagonal vault silhouette. Rift landing geometry has its own live-ROM
    # reachability suite and deliberately carves a broad cardinal cross.
    frost = generated_room(
        3, screenshot=ROOT / "tmp" / "frost-vault.png", local_room=4
    )
    assert_no_false_one_tile_gaps("Frost vault", frost)
    vault_sites = [
        (7, 5), (8, 5), (11, 5), (12, 5),
        (7, 12), (8, 12), (11, 12), (12, 12),
        (5, 6), (5, 7), (5, 10), (5, 11),
        (14, 6), (14, 7), (14, 10), (14, 11),
    ]
    vault_crystals = sum(tile(frost, x, y) == BGT_CRYSTAL for x, y in vault_sites)
    # The non-Rift sample preserves the complete silhouette while still
    # allowing seed-dependent base decoration around it.
    assert vault_crystals >= 10, f"Frost vault ring missing ({vault_crystals}/16)"
    # The four axial breaks are the visual language and the safety contract.
    assert all(tile(frost, x, y) != BGT_CRYSTAL for x, y in (
        (9, 5), (10, 5), (9, 12), (10, 12),
        (5, 8), (5, 9), (14, 8), (14, 9),
    ))
    frost_exits = reachable_exits(frost, (18, 9))
    assert_graph_exits("Frost vault", frost_exits, 3, 4)
    # Room seventeen is the later wing threshold. Sampling a different
    # archetype here proves both landmark slots survive into deep traversal.
    frost_wing = generated_room(
        3, local_room=17, probe=assert_waypoint_patrol
    )
    assert_no_false_one_tile_gaps("Frost late wing", frost_wing)
    frost_wing_crystals = sum(
        tile(frost_wing, x, y) == BGT_CRYSTAL for x, y in vault_sites
    )
    assert frost_wing_crystals >= 10, (
        f"Frost late-wing vault missing ({frost_wing_crystals}/16)"
    )
    assert_graph_exits(
        "Frost late wing", reachable_exits(frost_wing, (18, 9)), 3, 17,
        wide=True
    )

    def assert_mire_swim_passive(pb, tiles):
        # Remove combat noise, stand the feet-center on an actual pool tile,
        # and prove the class-specific hazard contract in the running ROM.
        for i in range(32):
            ep = EN + i * 28
            # A newly added pouncer can already have spawned its telegraph
            # effect/projectile; this terrain contract must clear *all*
            # non-player entity types rather than assuming only enemies can
            # interfere with the two-frame damage observation.
            pb.memory[ep] = pb.memory[ep + 1] = 0
        site = next((x, y) for y in range(4, 14) for x in range(4, 16)
                    if tile(tiles, x, y) == BGT_SPIKES)
        put16(pb, PL + 9, site[0] * 8 - 8)
        put16(pb, PL + 11, site[1] * 8 - 12)
        pb.memory[PL] = 3       # Picsean
        pb.memory[PL + 2] = 10
        pb.memory[PL + 15] = 0
        pb.tick(2)
        assert pb.memory[PL + 2] == 10, "Picsean swim passive did not cross mire safely"
        pb.memory[PL] = 1       # Sauran control: same tile must still hurt
        pb.memory[PL + 2] = 10
        pb.memory[PL + 15] = 0
        pb.tick(2)
        assert pb.memory[PL + 2] == 9, "mire hazard stopped damaging non-Picsean classes"

    mire_counts = []
    for index, seed in enumerate((0xCAFE1234, 0xCAFE1235, 0xCAFE1236, 0xCAFE1237)):
        sample_cell = archetype_sample_cell(4, seed)
        mire = generated_room(
            4, seed,
            screenshot=ROOT / "tmp" / "toxic-mire.png" if index == 0 else None,
            probe=assert_mire_swim_passive if index == 0 else None,
        )
        assert_no_false_one_tile_gaps(
            f"Toxic Mire seed={seed:#x}", mire)
        mire_spikes = sum(
            tile(mire, x, y) == BGT_SPIKES
            for x in (*range(4, 7), *range(13, 16))
            for y in (*range(4, 7), *range(11, 14))
        )
        mire_counts.append(mire_spikes)
        assert mire_spikes >= 24, (
            f"Toxic Mire island pools missing seed={seed:#x} ({mire_spikes}/36)"
        )
        # Unlike Ember's crossing seams, the bogs leave a broad central cross:
        # players can route between all four islands without mandatory damage.
        assert all(tile(mire, x, y) != BGT_SPIKES
                   for x in range(3, 17) for y in (8, 9))
        assert all(tile(mire, x, y) != BGT_SPIKES
                   for x in (9, 10) for y in range(3, 15))
        mire_exits = reachable_exits(mire, (18, 9))
        assert_graph_exits(
            f"Toxic Mire seed={seed:#x}", mire_exits, 4, sample_cell, seed,
            wide=True,
        )

    keep_counts = []
    for index, seed in enumerate((0x5A0D0000, 0x5A0D0001)):
        sample_cell = archetype_sample_cell(5, seed)
        keep = generated_room(
            5, seed,
            screenshot=ROOT / "tmp" / "shadow-keep.png" if index == 0 else None,
        )
        assert_no_false_one_tile_gaps(
            f"Shadow Keep seed={seed:#x}", keep)
        keep_pillars = sum(
            tile(keep, x, y) == BGT_PILLAR
            for x in range(4, 16) for y in (6, 11)
        )
        keep_counts.append(keep_pillars)
        # Room four preserves both complete portcullises: each twelve-tile row
        # owns a four-tile gate, leaving sixteen hard bars in the zig-zag keep.
        assert keep_pillars >= 8, (
            f"Shadow Keep portcullises missing seed={seed:#x} ({keep_pillars}/16)"
        )
        upper_gate = next((g for g in (5, 11)
                           if all(tile(keep, x, 6) != BGT_PILLAR
                                  for x in range(g, g + 4))), None)
        assert upper_gate is not None, "Shadow Keep upper gate disappeared"
        lower_gate = 11 if upper_gate == 5 else 5
        assert all(tile(keep, x, 6) != BGT_PILLAR
                   for x in range(upper_gate, upper_gate + 4))
        assert all(tile(keep, x, 11) != BGT_PILLAR
                   for x in range(lower_gate, lower_gate + 4))
        keep_exits = reachable_exits(keep, (18, 9))
        assert_graph_exits(
            f"Shadow Keep seed={seed:#x}", keep_exits, 5, sample_cell, seed,
            wide=True,
        )

    temple_signatures = []
    for index, seed in enumerate((0x601D0000, 0x601D0001)):
        sample_cell = archetype_sample_cell(6, seed)
        temple = generated_room(
            6, seed,
            screenshot=ROOT / "tmp" / "golden-temple.png" if index == 0 else None,
        )
        assert_no_false_one_tile_gaps(
            f"Golden Temple seed={seed:#x}", temple)
        colonnade_sites = [
            (x, y) for x in (5, 14) for y in (4, 5, 6, 11, 12, 13)
        ]
        pillars = sum(tile(temple, x, y) == BGT_PILLAR
                      for x, y in colonnade_sites)
        # The room-four landmark preserves the complete colonnade while Rift
        # landing safety remains covered independently in rooms two/eight.
        assert pillars >= 10, (
            f"Golden Temple colonnades missing seed={seed:#x} ({pillars}/12)"
        )
        inner_l = next((x for x in (6, 7)
                        if tile(temple, x, 5) == BGT_CRYSTAL), None)
        assert inner_l is not None, "Golden Temple left court marker disappeared"
        inner_r = 19 - inner_l
        crystal_sites = [(inner_l, 5), (inner_r, 5),
                         (inner_l, 12), (inner_r, 12)]
        crystals = sum(tile(temple, x, y) == BGT_CRYSTAL
                       for x, y in crystal_sites)
        # All four inner markers remain available in the dedicated landmark.
        assert crystals >= 3, (
            f"Golden Temple inner court missing seed={seed:#x} ({crystals}/4)"
        )
        # The processional aisle and transept are the archetype's safety and
        # visual contracts: a broad luminous cross remains unobstructed.
        assert all(tile(temple, x, y) not in (BGT_PILLAR, BGT_CRYSTAL)
                   for x in (9, 10) for y in range(3, 15))
        assert all(tile(temple, x, y) not in (BGT_PILLAR, BGT_CRYSTAL)
                   for x in range(3, 17) for y in (8, 9))
        temple_exits = reachable_exits(temple, (18, 9))
        assert_graph_exits(f"Golden Temple seed={seed:#x}",
                           temple_exits, 6, sample_cell, seed, wide=True)
        temple_signatures.append((pillars, crystals, inner_l))
    assert temple_signatures[0] != temple_signatures[1], (
        "Golden Temple seed variants collapsed to one inner-court layout"
    )

    blood_seed = 0xB100D007
    blood = generated_room(7, blood_seed,
                           screenshot=ROOT / "tmp" / "bloodmoon-sigil.png")
    assert_no_false_one_tile_gaps("Bloodmoon", blood)
    blood_sites = []
    for i in (4, 6):
        blood_sites.extend(((i, i), (19 - i, i),
                            (i, 17 - i), (19 - i, 17 - i)))
    blood_spikes = sum(tile(blood, x, y) == BGT_SPIKES
                       for x, y in blood_sites)
    # The dedicated landmark retains all eight mirrored ritual cuts.
    assert blood_spikes >= 7, (
        f"Bloodmoon ritual cuts missing ({blood_spikes}/8): "
        f"{[(site, tile(blood, *site)) for site in blood_sites]}"
    )
    assert all(tile(blood, x, y) != BGT_SPIKES
               for x in (9, 10) for y in range(3, 15))
    assert all(tile(blood, x, y) != BGT_SPIKES
               for x in range(3, 17) for y in (8, 9))
    blood_exits = reachable_exits(blood, (18, 9))
    assert_graph_exits("Bloodmoon", blood_exits, 7,
                       archetype_sample_cell(7, blood_seed), blood_seed,
                       wide=True)

    void_signatures = []
    void_sites = []
    for i in (4, 5):
        void_sites.extend(((i, i - 1), (19 - i, i - 1),
                           (i, 17 - i), (19 - i, 17 - i)))
    for index, seed in enumerate((0xA01D0000, 0xA01D0001,
                                  0xA01D0002, 0xA01D0003)):
        sample_cell = archetype_sample_cell(8, seed)
        void = generated_room(
            8, seed,
            screenshot=ROOT / "tmp" / "void-sanctum.png" if index == 0 else None,
        )
        assert_no_false_one_tile_gaps(
            f"Void Sanctum seed={seed:#x}", void)
        signature = tuple(tile(void, x, y) for x, y in void_sites)
        assert all(t in (BGT_PILLAR, BGT_CRYSTAL) for t in signature), (
            f"Void event horizon missing seed={seed:#x}"
        )
        assert signature.count(BGT_PILLAR) == 4
        assert signature.count(BGT_CRYSTAL) == 4
        assert all(tile(void, x, y) not in (BGT_PILLAR, BGT_CRYSTAL)
                   for x in (9, 10) for y in range(3, 15))
        assert all(tile(void, x, y) not in (BGT_PILLAR, BGT_CRYSTAL)
                   for x in range(3, 17) for y in (8, 9))
        void_exits = reachable_exits(void, (18, 9))
        assert_graph_exits(f"Void Sanctum seed={seed:#x}",
                           void_exits, 8, sample_cell, seed, wide=True)
        assert_escape_rails(f"Void Sanctum seed={seed:#x}", void)
        void_signatures.append(signature)
    # This is the exact final-stage landmark/seed that exposed a peripheral
    # underhang in the full controller replay: the hero could be knocked into
    # the lower-right pocket but full-sprite vertical collision could not
    # release them. Keep the room-four regression explicit.
    void_trap = generated_room(8, 2064128163, local_room=4)
    assert_escape_rails("Void Sanctum room-four replay", void_trap)
    assert_graph_exits(
        "Void Sanctum room-four replay",
        reachable_exits(void_trap, (18, 9)), 8, 4, 2064128163
    )
    assert len(set(void_signatures)) == 2, (
        "Void Sanctum seed variants collapsed or became unstable"
    )
    print(f"[stage-types] PASS Verdant grove={grove_crystals}/8, "
          f"wing={grove_wing_crystals}/8, "
          f"Ember seams={seam_spikes}/24, Frost vault={vault_crystals}/16, "
          f"late-wing={frost_wing_crystals}/16, "
          f"Toxic pools={min(mire_counts)}-{max(mire_counts)}/36 across 4 mirrors, "
          f"Shadow portcullises={min(keep_counts)}-{max(keep_counts)}/16, "
          "Golden colonnades=12/12 + court=4/4 across 2 insets, "
          f"Blood cuts={blood_spikes}/8, "
          "Void horizon=8/8 across 4 mirrored seeds, "
          "all authored graph exits reachable")


if __name__ == "__main__":
    main()
