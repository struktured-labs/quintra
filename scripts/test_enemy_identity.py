#!/usr/bin/env python3
"""Regression: specialist IDs map to four unique OBJ tiles loaded by the ROM."""
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
ENEMY_HEADER = (ROOT / "src/generated/enemies.h").read_text()
ENEMY_SOURCE = (ROOT / "src/generated/enemies.c").read_text()
SPAWN_SOURCE = (ROOT / "src/game/enemy_ai.c").read_text()
SPRITE_SOURCE = (ROOT / "src/render/sprites_gen.c").read_text()

IDENTITIES = {
    0: (20, 3), 1: (24, 6), 2: (21, 5), 3: (22, 0), 4: (56, 7),
    5: (34, 0), 6: (60, 4), 7: (37, 0), 8: (64, 7), 9: (39, 7),
    10: (68, 3), 11: (72, 5), 12: (73, 0), 13: (74, 4),
    14: (75, 3), 15: (76, 7), 16: (77, 0), 17: (78, 7),
    18: (80, 5), 19: (124, 6), 20: (125, 4), 21: (81, 6),
    22: (69, 6), 23: (79, 6),
    27: (79, 7),
}

SPECIALISTS = {
    11: (72, 37, "FOLD_STAR", "SPR_ENEMY_FOLD_STAR", "fold-star"),
    12: (73, 21, "FLUTTERBAT", "SPR_ENEMY_FLUTTERBAT", "flutterbat"),
    13: (74, 34, "GLOAM_LEECH", "SPR_ENEMY_GLOAM_LEECH", "gloam-leech"),
    14: (75, 20, "CINDER_MAW", "SPR_ENEMY_CINDER_MAW", "cinder-maw"),
    15: (76, 20, "RIFT_OOZE", "SPR_ENEMY_RIFT_OOZE", "rift-ooze"),
    16: (77, 21, "MIRROR_MOTH", "SPR_ENEMY_MIRROR_MOTH", "mirror-moth"),
    17: (78, 20, "MIRE_SPORE", "SPR_ENEMY_MIRE_SPORE", "mire-spore"),
    18: (80, 68, "ECHO_GUARD", "SPR_ENEMY_ECHO_GUARD", "echo-guard"),
    19: (124, 75, "RUNE_LANTERN", "SPR_ENEMY_RUNE_LANTERN", "rune-lantern"),
    20: (125, 124, "DREAD_BELL", "SPR_ENEMY_DREAD_BELL", "dread-bell"),
    21: (81, 35, "RIFT_WARDEN", "SPR_ENEMY_RIFT_WARDEN", "rift-warden"),
    22: (69, 20, "PRISM_SKITTER", "SPR_ENEMY_PRISM_SKITTER", "prism-skitter"),
    23: (79, 71, "DUSK_MIDGE", "SPR_ENEMY_DUSK_MIDGE", "dusk-midge"),
}


def put_fix8(pb, address, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (i * 8)) & 0xFF


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


def generated_sprite(name):
    match = re.search(rf"const u8 {name}\[16\] = \{{([^}}]+)\}};", SPRITE_SOURCE)
    if not match:
        raise RuntimeError(f"missing generated sprite {name}")
    return bytes(int(token.strip(), 0) for token in match.group(1).split(",") if token.strip())


def main():
    assert "e->sprite_tile = def->sprite_set;" in SPAWN_SOURCE
    assert "e->palette     = def->palette;" in SPAWN_SOURCE
    assert "sprite_for_enemy" not in SPAWN_SOURCE
    assert "palette_for_enemy" not in SPAWN_SOURCE
    room_source = (ROOT / "src/game/room.c").read_text()
    assert "tiles_load_dread_bell_sprite" in room_source
    assert "tiles_load_dusk_midge_sprite" in room_source
    assert "tiles_load_sunwheel_sprite" in room_source
    assert "!RUN_ROOM_IS_TOWN(run_state.room_counter)" in room_source
    assert "room_state_has_shop_wares" in room_source
    # Generated content is the sole runtime identity source. Pin every roster
    # entry's hardware OBJ slot/palette so no hand-written C switch can drift.
    for enemy_id, (slot, palette) in IDENTITIES.items():
        enemy_symbol = next(v[2] for k, v in SPECIALISTS.items() if k == enemy_id) \
            if enemy_id in SPECIALISTS else None
        if enemy_symbol:
            id_pattern = rf"#define\s+ENEMY_{enemy_symbol}\s+{enemy_id}\b"
            assert re.search(id_pattern, ENEMY_HEADER), f"enemy {enemy_id} generated ID drifted"
        record = rf'\{{ \.id={enemy_id}, \.name="[^"]+", \.sprite_set={slot}, \.palette={palette},'
        assert re.search(record, ENEMY_SOURCE), f"enemy {enemy_id} generated identity drifted"

    for enemy_id, (_, _, enemy_symbol, _, name) in SPECIALISTS.items():
        id_pattern = rf"#define\s+ENEMY_{enemy_symbol}\s+{enemy_id}\b"
        assert re.search(id_pattern, ENEMY_HEADER), f"{name} generated ID drifted"

    # Boot the real cartridge so room_enter loads OBJ VRAM through the same
    # loader used by gameplay, then compare the compiled 2bpp tiles.
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    assert pb.memory[addr("_music_track_id")] == 18, "ROM did not boot to title"
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(240):
        pb.tick()
    tiles = {}
    for enemy_id, (slot, legacy_slot, _, _, name) in SPECIALISTS.items():
        tile = bytes(pb.memory[0x8000 + slot * 16 + i] for i in range(16))
        legacy = bytes(pb.memory[0x8000 + legacy_slot * 16 + i] for i in range(16))
        assert any(tile), f"{name} OBJ tile is blank in runtime VRAM"
        assert tile != legacy, f"{name} still aliases its legacy silhouette"
        tiles[enemy_id] = tile
    assert len(set(tiles.values())) == len(SPECIALISTS), "specialist OBJ silhouettes are not unique"

    # Slot 125 is deliberately multiplexed.  In combat it holds Dread Bell
    # art, but the real room transition into a merchant room must restore the
    # proximity-callout sprite. This catches a loader-order regression that a
    # static source guard cannot see.
    dread_tile = bytes(pb.memory[0x8000 + 125 * 16:0x8000 + 126 * 16])
    assert dread_tile == tiles[20], "combat room did not install Dread Bell art"
    pb.memory[addr("_run_state") + 1] = 3
    pb.memory[addr("_run_state") + 17] = 1
    pb.memory[addr("_run_state") + 18] = 6
    put16(pb, addr("_player") + 9, 72)
    put16(pb, addr("_player") + 11, 60)
    pb.memory[addr("_room_tilemap") + 9 * 20 + 10] = 34
    for _ in range(30):
        pb.tick()
        if pb.memory[addr("_run_state") + 1] == 4:
            break
    assert pb.memory[addr("_run_state") + 1] == 4, "could not enter merchant room"
    entities = addr("_entities")
    merchant_count = 0
    for _ in range(60):
        pb.tick()
        merchant_count = sum(
            pb.memory[entities + i * 28] == 3
            and pb.memory[entities + i * 28 + 1] & 1
            and pb.memory[entities + i * 28 + 17] == 8
            for i in range(32)
        )
        if merchant_count == 1:
            break
    assert merchant_count == 1, f"room 4 did not generate its merchant: {merchant_count}"
    callout = generated_sprite("sprite_fx_merchant_callout")
    actual_callout = bytes(pb.memory[0x8000 + 125 * 16:0x8000 + 126 * 16])
    assert actual_callout == callout, (
        "merchant room retained Dread Bell art in callout slot: "
        f"got={actual_callout.hex()} expected={callout.hex()} "
        f"room={pb.memory[addr('_run_state') + 1]} "
        f"world={pb.memory[addr('_run_state') + 17]}"
    )

    # Put a live leech across a long pillar wall from the player. Its edge
    # slide must route around cover through the real enemy update loop;
    # otherwise direct homing keeps a sealed room alive indefinitely.
    entities = addr("_entities")
    player = addr("_player")
    tilemap = addr("_room_tilemap")
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    for i in range(20 * 17):
        pb.memory[tilemap + i] = 1
    wall_x = 12
    for wall_y in range(3, 15):
        pb.memory[tilemap + wall_y * 20 + wall_x] = 2
    put16(pb, player + 9, 8 * 8)
    put16(pb, player + 11, 12 * 8)
    leech = entities
    pb.memory[leech] = 2
    pb.memory[leech + 1] = 3
    put_fix8(pb, leech + 2, 15 * 8)
    put_fix8(pb, leech + 6, 12 * 8)
    pb.memory[leech + 14] = 4
    pb.memory[leech + 17] = 13
    pb.memory[leech + 25] = 0x66
    frame_counter = addr("_loop_frame_counter")
    before_frames = pb.memory[frame_counter] | (pb.memory[frame_counter + 1] << 8)
    for _ in range(900):
        pb.tick()
    after_frames = pb.memory[frame_counter] | (pb.memory[frame_counter + 1] << 8)
    escaped_x, escaped_y = pb.memory[leech + 3], pb.memory[leech + 7]
    assert escaped_x < wall_x * 8, (
        f"Gloom Leech never routed around cover: {escaped_x},{escaped_y}; "
        f"stuck={pb.memory[leech + 21]} state_timer={pb.memory[leech + 16]} "
        f"flags={pb.memory[leech + 1]} screen={pb.memory[addr('_loop_current_screen')]} "
        f"hp={pb.memory[player + 2]} room={pb.memory[addr('_run_state') + 1]} "
        f"hitstop={pb.memory[addr('_g_hitstop')]} pause={pb.memory[tilemap + 340]}"
        f" loop_frames={before_frames}->{after_frames}"
    )

    # A Flutterbat can fit into a diagonal notch that the champion's wider
    # feet-box cannot enter. Recreate that exact corner: NE is blocked by the
    # tile above, while east is open. Its cardinal fallback must escape rather
    # than repeatedly settling there and softlocking a sealed melee room.
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    for i in range(20 * 17):
        pb.memory[tilemap + i] = 1
    pb.memory[tilemap + 9 * 20 + 10] = 2
    bat = entities
    pb.memory[bat] = 2
    pb.memory[bat + 1] = 3
    put_fix8(pb, bat + 2, 80)
    put_fix8(pb, bat + 6, 79)
    pb.memory[bat + 14] = 2
    pb.memory[bat + 15] = 1       # flutter phase
    pb.memory[bat + 16] = 1       # move on the next update
    pb.memory[bat + 17] = 12
    pb.memory[bat + 19] = 1       # NE diagonal seed
    pb.memory[bat + 25] = 0x66
    pb.memory[player + 2] = 20
    pb.memory[addr("_g_hitstop")] = 0
    for _ in range(20):
        pb.tick()
        if pb.memory[bat + 3] != 80 or pb.memory[bat + 7] != 79:
            break
    assert pb.memory[bat + 3] > 80 and pb.memory[bat + 7] == 79, (
        f"Flutterbat did not cardinal-fallback out of notch: "
        f"{pb.memory[bat + 3]},{pb.memory[bat + 7]}"
    )

    # A persistent Skeleton chaser must not enter a one-tile lane that the
    # hero's 12px feet box cannot occupy.  Before the Skeleton-specific
    # clearance, it could pursue through this lane and strand a melee run in
    # a sealed room.  The same direct chase also exercises both perpendicular
    # fallback attempts rather than only a static collision predicate.
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    for i in range(20 * 17):
        pb.memory[tilemap + i] = 1
    for tx in range(1, 19):
        pb.memory[tilemap + 7 * 20 + tx] = 2
        pb.memory[tilemap + 9 * 20 + tx] = 2
    put16(pb, player + 9, 120)
    put16(pb, player + 11, 64)
    skeleton = entities
    pb.memory[skeleton] = 2
    pb.memory[skeleton + 1] = 3
    put_fix8(pb, skeleton + 2, 64)
    put_fix8(pb, skeleton + 6, 64)
    pb.memory[skeleton + 14] = 10
    pb.memory[skeleton + 16] = 2  # Skeleton (speed 64) steps next tick
    pb.memory[skeleton + 17] = 3
    pb.memory[skeleton + 25] = 0x66
    pb.memory[addr("_g_hitstop")] = 0
    for _ in range(20):
        pb.tick()
    assert (pb.memory[skeleton + 3], pb.memory[skeleton + 7]) == (64, 64), (
        "Skeleton entered a champion-inaccessible one-tile lane: "
        f"{pb.memory[skeleton + 3]},{pb.memory[skeleton + 7]}"
    )

    # Gloom Leeches are also persistent chasers, but their old 8px movement
    # envelope could cross this exact one-tile lane and latch from a pocket
    # a champion cannot physically enter. Their Metroid-like drain remains
    # dangerous in open rooms; this only preserves a fair player-sized route.
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    for i in range(20 * 17):
        pb.memory[tilemap + i] = 1
    for tx in range(1, 19):
        pb.memory[tilemap + 7 * 20 + tx] = 2
        pb.memory[tilemap + 9 * 20 + tx] = 2
    put16(pb, player + 9, 120)
    put16(pb, player + 11, 64)
    leech = entities
    pb.memory[leech] = 2
    pb.memory[leech + 1] = 3
    put_fix8(pb, leech + 2, 64)
    put_fix8(pb, leech + 6, 64)
    pb.memory[leech + 14] = 10
    pb.memory[leech + 16] = 2  # Gloom Leech (speed 72) steps next tick
    pb.memory[leech + 17] = 13
    pb.memory[leech + 25] = 0x66
    pb.memory[addr("_g_hitstop")] = 0
    for _ in range(20):
        pb.tick()
    assert (pb.memory[leech + 3], pb.memory[leech + 7]) == (64, 64), (
        "Gloom Leech entered a champion-inaccessible one-tile lane: "
        f"{pb.memory[leech + 3]},{pb.memory[leech + 7]}"
    )

    # Mirror Moth runs through its typed AI_MIRROR dispatch in bank 3. Real
    # controller movement to the right must make it step left, and its authored
    # fire clock must produce a hostile reflected bolt without direct writes.
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    for i in range(20 * 17):
        pb.memory[tilemap + i] = 1
    put16(pb, player + 9, 64)
    put16(pb, player + 11, 72)
    pb.memory[player + 2] = 20
    moth = entities
    pb.memory[moth] = 2
    pb.memory[moth + 1] = 3
    put_fix8(pb, moth + 2, 112)
    put_fix8(pb, moth + 6, 72)
    pb.memory[moth + 14] = 4
    pb.memory[moth + 17] = 16
    pb.memory[moth + 18] = 116      # four ticks from reflected fire
    pb.memory[moth + 25] = 0x66
    pb.memory[addr("_g_hitstop")] = 0
    pb.tick()                        # initialize last-player sample
    player_x0, moth_x0 = pb.memory[player + 9], pb.memory[moth + 3]
    pb.button_press("right")
    for _ in range(18):
        pb.tick()
    pb.button_release("right")
    assert pb.memory[player + 9] > player_x0, "controller did not move hero right"
    assert pb.memory[moth + 3] < moth_x0, (
        f"Mirror Moth did not reverse hero movement: {moth_x0}->{pb.memory[moth + 3]}"
    )
    reflected = []
    for i in range(1, 32):
        ep = entities + i * 28
        if pb.memory[ep] == 1 and pb.memory[ep + 1] & 1:
            reflected.append((pb.memory[ep + 5], pb.memory[ep + 9]))
    assert reflected, "Mirror Moth did not fire its reflected hostile bolt"

    # A Mire Spore must remain inert at range, arm only inside its authored
    # 40px Manhattan radius, honor the 36-frame tell, then produce all eight
    # hostile lanes through the actual banked dispatch.
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    for i in range(20 * 17):
        pb.memory[tilemap + i] = 1
    put16(pb, player + 9, 32)
    put16(pb, player + 11, 32)
    pb.memory[player + 2] = 20
    spore = entities
    pb.memory[spore] = 2
    pb.memory[spore + 1] = 3
    put_fix8(pb, spore + 2, 112)
    put_fix8(pb, spore + 6, 80)
    pb.memory[spore + 14] = 5
    pb.memory[spore + 17] = 17
    pb.memory[spore + 25] = 0x66
    for _ in range(20):
        pb.tick()
    assert pb.memory[spore + 15] == 0, "Mire Spore armed outside trigger radius"
    put16(pb, player + 9, 88)
    put16(pb, player + 11, 80)
    pb.tick()
    assert pb.memory[spore + 15] == 1, "Mire Spore did not arm near hero"
    assert pb.memory[spore + 18] >= 34, "Mire Spore skipped its readable fuse"
    for _ in range(40):
        pb.tick()
    spores = []
    for i in range(1, 32):
        ep = entities + i * 28
        if pb.memory[ep] == 1 and pb.memory[ep + 1] & 1:
            spores.append((pb.memory[ep + 5], pb.memory[ep + 9]))
    assert len(spores) == 8, f"Mire Spore radial burst drifted: {spores}"
    assert pb.memory[spore + 15] == 2, "Mire Spore did not enter punish recovery"

    # Echo Guard must consume the first real player attack without losing HP,
    # rush toward the attacker, then accept damage while its shield is down.
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    for i in range(20 * 17):
        pb.memory[tilemap + i] = 1
    put16(pb, player + 9, 120)
    put16(pb, player + 11, 72)
    pb.memory[player + 2] = 20
    pb.memory[player + 8] = 0       # no crit chance
    guard = entities
    shot = entities + 28
    pb.memory[guard] = 2
    pb.memory[guard + 1] = 3
    put_fix8(pb, guard + 2, 80)
    put_fix8(pb, guard + 6, 72)
    pb.memory[guard + 12] = 80
    pb.memory[guard + 13] = 5
    pb.memory[guard + 14] = 7
    pb.memory[guard + 17] = 18
    pb.memory[guard + 25] = 0x66
    pb.memory[shot] = 1
    pb.memory[shot + 1] = 0x13
    put_fix8(pb, shot + 2, 80)
    put_fix8(pb, shot + 6, 72)
    pb.memory[shot + 14] = 2
    pb.memory[shot + 16] = 30
    pb.memory[shot + 17] = 0
    pb.memory[shot + 25] = 0x77
    pb.memory[shot + 27] = 1
    pb.memory[addr("_g_hitstop")] = 0
    pb.tick()
    assert pb.memory[guard + 14] == 7, "Echo Guard's ready shield leaked damage"
    assert pb.memory[guard + 15] == 1 and pb.memory[guard + 23] > 90, (
        "Echo Guard did not enter its counter cooldown: "
        f"state={pb.memory[guard + 15]} cooldown={pb.memory[guard + 23]} "
        f"shot_flags={pb.memory[shot + 1]}"
    )
    assert not (pb.memory[shot + 1] & 1), "Echo Guard did not spend the parried shot"
    guard_x0 = pb.memory[guard + 3]
    for _ in range(10):
        pb.tick()
    assert pb.memory[guard + 3] > guard_x0, "Echo Guard did not rush the attacker"
    put_fix8(pb, shot + 2, pb.memory[guard + 3])
    put_fix8(pb, shot + 6, pb.memory[guard + 7])
    pb.memory[shot] = 1
    pb.memory[shot + 1] = 0x13
    pb.memory[shot + 14] = 2
    pb.memory[shot + 16] = 30
    pb.memory[shot + 17] = 0
    pb.memory[shot + 25] = 0x77
    pb.memory[shot + 27] = 1
    pb.tick()
    assert pb.memory[guard + 14] < 7, "Echo Guard stayed invulnerable after its parry"

    # Kill a Rift Ooze through the real projectile/combat loop. The corpse
    # must become two fragile crawler fragments, not merely claim to split in
    # authored data or a unit-test-only helper.
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    for i in range(20 * 17):
        pb.memory[tilemap + i] = 1
    ooze = entities
    shot = entities + 28
    # Saturate all other slots with harmless long-lived FX. Both fragments
    # must still appear, proving the lethal shot is released early enough.
    for i in range(2, 32):
        filler = entities + i * 28
        pb.memory[filler] = 4
        pb.memory[filler + 1] = 3
        pb.memory[filler + 16] = 100
    pb.memory[ooze] = 2
    pb.memory[ooze + 1] = 3
    put_fix8(pb, ooze + 2, 80)
    put_fix8(pb, ooze + 6, 72)
    pb.memory[ooze + 14] = 1
    pb.memory[ooze + 16] = 30
    pb.memory[ooze + 17] = 15
    pb.memory[ooze + 25] = 0x66
    pb.memory[ooze + 27] = 1
    pb.memory[shot] = 1
    pb.memory[shot + 1] = 0x13
    put_fix8(pb, shot + 2, 80)
    put_fix8(pb, shot + 6, 72)
    pb.memory[shot + 14] = 1
    pb.memory[shot + 16] = 10
    pb.memory[shot + 25] = 0x77
    pb.memory[shot + 27] = 1
    pb.memory[addr("_g_hitstop")] = 0
    for _ in range(4):
        pb.tick()
    fragments = []
    for i in range(32):
        e = entities + i * 28
        if pb.memory[e] == 2 and pb.memory[e + 1] & 1:
            fragments.append((pb.memory[e + 17], pb.memory[e + 14]))
    assert fragments.count((0, 2)) == 2, f"Rift Ooze split drifted: {fragments}"
    assert all(enemy_id != 15 for enemy_id, _ in fragments), (
        f"dead Rift Ooze remained active: {fragments}"
    )

    # Rune Lantern is the late-game moving ring caster. Its authored four
    # cardinal lanes must emerge from the real AI_SHOOTER dispatch, leaving
    # the diagonals as visible escape paths instead of becoming a data-only
    # roster entry or a generic single-shot wisp.
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    for i in range(20 * 17):
        pb.memory[tilemap + i] = 1
    put16(pb, player + 9, 32)
    put16(pb, player + 11, 32)
    pb.memory[player + 2] = 20
    lantern = entities
    pb.memory[lantern] = 2
    pb.memory[lantern + 1] = 3
    put_fix8(pb, lantern + 2, 88)
    put_fix8(pb, lantern + 6, 72)
    pb.memory[lantern + 14] = 8
    pb.memory[lantern + 17] = 19
    pb.memory[lantern + 18] = 0       # fire immediately
    pb.memory[lantern + 25] = 0x66
    pb.memory[addr("_g_hitstop")] = 0
    pb.tick()
    ring = []
    for i in range(1, 32):
        ep = entities + i * 28
        if pb.memory[ep] == 1 and pb.memory[ep + 1] & 1:
            vx, vy = pb.memory[ep + 10], pb.memory[ep + 11]
            ring.append((vx - 256 if vx >= 128 else vx,
                         vy - 256 if vy >= 128 else vy))
    assert set(ring) == {(2, 0), (-2, 0), (0, 2), (0, -2)}, (
        f"Rune Lantern cardinal ring drifted: {ring}"
    )

    # Dread Bell is the heavier late-game lane check: a deliberately slow
    # cadence, but a full fast eight-way peal. It must exercise the generated
    # Ring(8) data and its special 3px/tick velocity through live AI, rather
    # than only occupying a weighted roster slot.
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    for i in range(20 * 17):
        pb.memory[tilemap + i] = 1
    put16(pb, player + 9, 32)
    put16(pb, player + 11, 32)
    pb.memory[player + 2] = 20
    bell = entities
    pb.memory[bell] = 2
    pb.memory[bell + 1] = 3
    put_fix8(pb, bell + 2, 88)
    put_fix8(pb, bell + 6, 72)
    pb.memory[bell + 12] = 125
    pb.memory[bell + 14] = 17
    pb.memory[bell + 17] = 20
    pb.memory[bell + 18] = 0          # peal immediately
    pb.memory[bell + 25] = 0x66
    pb.memory[addr("_g_hitstop")] = 0
    pb.tick()
    peal = []
    for i in range(1, 32):
        ep = entities + i * 28
        if pb.memory[ep] == 1 and pb.memory[ep + 1] & 1:
            vx, vy = pb.memory[ep + 10], pb.memory[ep + 11]
            peal.append((vx - 256 if vx >= 128 else vx,
                         vy - 256 if vy >= 128 else vy))
    assert set(peal) == {
        (3, 0), (3, 3), (0, 3), (-3, 3),
        (-3, 0), (-3, -3), (0, -3), (3, -3),
    }, f"Dread Bell eight-way fast peal drifted: {peal}"

    # Rift Warden is the new late-stage center-lane breaker. Its five-way fan
    # must differ from both the Lantern's cardinal ring and the Bell's full
    # peal, while slot 81 proves combat safely reclaims merchant-only tag art.
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    for i in range(20 * 17):
        pb.memory[tilemap + i] = 1
    put16(pb, player + 9, 32)
    put16(pb, player + 11, 72)
    pb.memory[player + 2] = 20
    warden = entities
    pb.memory[warden] = 2
    pb.memory[warden + 1] = 3
    put_fix8(pb, warden + 2, 88)
    put_fix8(pb, warden + 6, 72)
    pb.memory[warden + 12] = 81
    pb.memory[warden + 14] = 16
    pb.memory[warden + 16] = 1       # keep the pre-fire aim on a clean row
    pb.memory[warden + 17] = 21
    pb.memory[warden + 18] = 0       # fan immediately
    pb.memory[warden + 25] = 0x66
    pb.memory[addr("_g_hitstop")] = 0
    pb.tick()
    fan = []
    for i in range(1, 32):
        ep = entities + i * 28
        if pb.memory[ep] == 1 and pb.memory[ep + 1] & 1:
            vx, vy = pb.memory[ep + 10], pb.memory[ep + 11]
            fan.append((vx - 256 if vx >= 128 else vx,
                        vy - 256 if vy >= 128 else vy))
    assert set(fan) == {(-2, -2), (-2, 0), (-2, 2), (0, -2), (0, 2)}, (
        f"Rift Warden five-way fan drifted: {fan}")

    # Prism Skitter activates the previously-unused typed AI_SPINNER path.
    # Its job is positional rather than another dense volley: at its authored
    # 40px ring it takes a tangential step, then rotates a sparse opposite
    # pair. This proves both movement and projectile identity through the
    # real banked enemy dispatch, not merely generated content metadata.
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    for i in range(20 * 17):
        pb.memory[tilemap + i] = 1
    put16(pb, player + 9, 80)
    put16(pb, player + 11, 72)
    pb.memory[player + 2] = 20
    skitter = entities
    pb.memory[skitter] = 2
    pb.memory[skitter + 1] = 3
    put_fix8(pb, skitter + 2, 40)
    put_fix8(pb, skitter + 6, 72)
    pb.memory[skitter + 12] = 69
    pb.memory[skitter + 14] = 14
    pb.memory[skitter + 16] = 2       # orbit step on the next update
    pb.memory[skitter + 17] = 22
    pb.memory[skitter + 18] = 0       # rotating pair immediately
    pb.memory[skitter + 19] = 0       # first pair is N/S
    pb.memory[skitter + 25] = 0x66
    pb.memory[skitter + 26] = 2
    pb.memory[addr("_g_hitstop")] = 0
    pb.tick()
    assert pb.memory[skitter + 7] < 72, (
        f"Prism Skitter did not take a tangential orbit step: "
        f"{pb.memory[skitter + 3]},{pb.memory[skitter + 7]}")
    skitter_pair = []
    for i in range(1, 32):
        ep = entities + i * 28
        if pb.memory[ep] == 1 and pb.memory[ep + 1] & 1:
            vx, vy = pb.memory[ep + 10], pb.memory[ep + 11]
            skitter_pair.append((vx - 256 if vx >= 128 else vx,
                                 vy - 256 if vy >= 128 else vy))
    assert set(skitter_pair) == {(0, -2), (0, 2)}, (
        f"Prism Skitter opposite pair drifted: {skitter_pair}")
    pb.stop(save=False)
    print("[enemy-id] PASS specialist art (including Dusk Midge) + "
          "guard/spore/mirror/leech/lantern/bell/warden/skitter behavior + ooze split")


if __name__ == "__main__":
    main()
