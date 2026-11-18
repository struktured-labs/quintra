#!/usr/bin/env python3
"""Shared fixtures for the 2026-11-17 specialist tests (+ basilisk tiers)."""
from test_will_max import boot, clear_arena, addr, put16, PLAYER, ENTITIES, TILEMAP

ENTITY_SIZE = 28
ENEMY_VEIL_MAGUS = 35
ENEMY_HEX_WALKER = 36
ENEMY_VAULT_HAND = 37
ENEMY_BANE_BRUTE = 38
ENEMY_ZAG_DART = 39
ENEMY_LEYBEAM = 40
ENEMY_FUSE_HURLER = 41
ENEMY_SUN_BASILISK = 42
ENEMY_NOX_BASILISK = 43

# entity_t
OFF_TYPE, OFF_FLAGS = 0, 1
OFF_X, OFF_Y = 3, 7
OFF_HP, OFF_STATE, OFF_TIMER = 14, 15, 16
OFF_ID = 17          # ai_data[0]
OFF_AI1 = 18         # TIMER
OFF_AI2 = 19         # PHASE
OFF_HITBOX, OFF_DAMAGE = 25, 26


def slot(i=0):
    return ENTITIES + i * ENTITY_SIZE


def poke_enemy(pb, enemy_id, x, y, hp=8, i=0, phase=0, timer=0, hitbox=0x66, damage=1):
    e = slot(i)
    for n in range(ENTITY_SIZE):
        pb.memory[e + n] = 0
    pb.memory[e + OFF_TYPE] = 2
    pb.memory[e + OFF_FLAGS] = 0x07  # ACTIVE|ALIVE|ON_SCREEN
    put16(pb, e + OFF_X, x)
    put16(pb, e + OFF_Y, y)
    pb.memory[e + OFF_HP] = hp
    pb.memory[e + OFF_STATE] = 0
    pb.memory[e + OFF_TIMER] = 0
    pb.memory[e + OFF_ID] = enemy_id
    pb.memory[e + OFF_AI1] = timer
    pb.memory[e + OFF_AI2] = phase
    pb.memory[e + OFF_HITBOX] = hitbox
    pb.memory[e + OFF_DAMAGE] = damage
    # A real spawn raises this so the specialist draw/bomb pass runs.
    pb.memory[addr('_new_monsters_in_room')] = 1
    return e


def pos(pb, e, off):
    return pb.memory[e + off] | (pb.memory[e + off + 1] << 8)


def set_dungeon_cell(pb, room=5, stage=0):
    """Leave the foyer so Vault Hand and specialists may act."""
    rs = addr('_run_state')
    pb.memory[rs + 1] = room
    pb.memory[rs + 11] = stage
    pb.memory[rs + 17] = 0  # world_mode off
    # encounter flags that might mark a boss
    try:
        pb.memory[addr('_room_encounter_kind')] = 0
        pb.memory[addr('_room_encounter_phase')] = 0
    except RuntimeError:
        pass


def spawn_arena(pb, class_id=0):
    clear_arena(pb)
    set_dungeon_cell(pb)
    put16(pb, PLAYER + 9, 80)
    put16(pb, PLAYER + 11, 72)
    pb.memory[PLAYER + 15] = 120  # iframes / will? patterns used +15 as iframes-like
    return pb
