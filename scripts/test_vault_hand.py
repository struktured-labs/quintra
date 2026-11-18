#!/usr/bin/env python3
"""Vault Hand mash-escape, mid-grab death, and foyer-restore keep inventory."""
from quintra_new_monsters import (
    boot, spawn_arena, poke_enemy, pos, set_dungeon_cell, addr, PLAYER, ENTITIES,
    ENEMY_VAULT_HAND, OFF_X, OFF_Y, OFF_AI2, OFF_HP, ENTITY_SIZE,
)
from test_will_max import put16

def holding(pb):
    try:
        return pb.memory[addr("_vault_hand_holding")]
    except RuntimeError:
        return 0

def main():
    # Mash escape: start already in the grab phase on top of the hero.
    pb = boot(0)
    spawn_arena(pb)
    put16(pb, PLAYER + 9, 80)
    put16(pb, PLAYER + 11, 72)
    e = poke_enemy(pb, ENEMY_VAULT_HAND, 80, 72, hp=16, phase=3, timer=0, hitbox=0xDD)
    escaped = False
    for frame in range(80):
        btn = ("a", "b", "left", "right", "up", "down")[frame % 6]
        pb.button_press(btn)
        pb.tick(1)
        pb.button_release(btn)
        pb.tick(1)
        if not holding(pb) and pb.memory[e + OFF_AI2] == 4:
            escaped = True
            break
    assert escaped, f"mash did not break the grab (phase={pb.memory[e+OFF_AI2]} hold={holding(pb)})"
    assert pb.memory[addr("_pending_foyer_warp")] == 0
    pb.stop(save=False)

    # Mid-grab death releases the hero and does not warp.
    pb = boot(0)
    spawn_arena(pb)
    put16(pb, PLAYER + 9, 80)
    put16(pb, PLAYER + 11, 72)
    e = poke_enemy(pb, ENEMY_VAULT_HAND, 80, 72, hp=16, phase=3, timer=0, hitbox=0xDD)
    pb.tick(2)
    pb.memory[e + OFF_HP] = 0
    for _ in range(8):
        pb.tick()
    assert holding(pb) == 0, "killed Hand kept holding"
    assert pb.memory[addr("_pending_foyer_warp")] == 0
    pb.stop(save=False)

    # Foyer carry: inventory is preserved (coins / pack bytes).
    pb = boot(0)
    spawn_arena(pb)
    # Seed a recognizable pack and coin count.
    pb.memory[PLAYER + 2] = 8  # hp
    # Packed player_state_t: coins at +16, inventory starts at +24.
    coins = addr("_player") + 16
    pack = addr("_player") + 24
    pb.memory[coins] = 0x2A
    pb.memory[coins + 1] = 0x00
    pb.memory[pack] = 0x51
    put16(pb, PLAYER + 9, 80)
    put16(pb, PLAYER + 11, 72)
    e = poke_enemy(pb, ENEMY_VAULT_HAND, 80, 72, hp=16, phase=3, timer=47, hitbox=0xDD)
    # Let the grab timer expire (grab_t default 48).
    for _ in range(8):
        pb.memory[PLAYER + 15] = 0
        pb.tick()
    for _ in range(90):
        pb.tick()
        if pb.memory[addr("_pending_foyer_warp")] == 0:
            break
    got_coins = pb.memory[coins] | (pb.memory[coins + 1] << 8)
    got_pack = pb.memory[pack]
    room = pb.memory[addr("_run_state") + 1]
    assert got_pack == 0x51, f"foyer carry dropped pack item {got_pack:#x} coins={got_coins:#x} room={room}"
    assert got_coins == 0x2A, f"foyer carry dropped coins {got_coins:#x} pack={got_pack:#x} room={room}"
    pb.stop(save=False)
    print("[vault-hand] PASS mash escape, mid-grab death, inventory kept room", room)

if __name__ == "__main__":
    main()
