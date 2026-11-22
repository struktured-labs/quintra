#pragma bank 30
// Register-only scan for the plain cases of the compact-room entity OAM
// allocator (entity_draw_all). It walks the rotated slot order from edr_i
// and places every plain 8x8 effect, ordinary player/enemy shot and plain
// small on-screen enemy exactly as entity_draw_fast would, stopping at the
// first active slot that needs the general C path. The caller handles that
// one slot and calls again, so OAM order is unchanged.
//
// SDCC kept ~20 live values in the general loop and spilled the entity
// pointer on every field access: ~1k clocks per plain sprite. This is ~150.
//
// In:  edr_i (first logical index), edr_rot (anim rotation), edr_oam.
// Out: edr_oam advanced; edr_i = index needing the general path, or 32.
#include <gb/gb.h>
#include "core/types.h"
#include "game/entity.h"
#include "game/entity_draw_run.h"

u8 edr_i, edr_rot, edr_oam;

void entity_draw_run(void) BANKED __naked {
    __asm
    11100$:                         ; loop
        ld  a, (_edr_i)
        cp  a, #32
        ret nc
        ld  b, a
        ld  a, (_edr_rot)
        add a, b
        and a, #31
        ld  c, a                    ; c = slot
        ld  l, a                    ; hl = entities + slot * 28
        ld  h, #0
        ld  d, h
        ld  e, l
        add hl, hl
        add hl, de
        add hl, hl
        add hl, de
        add hl, hl
        add hl, hl
        ld  de, #_entities
        add hl, de
        inc hl
        ld  a, (hl-)                ; flags
        bit 0, a
        jp  z, 11190$               ; inactive
        ld  b, a                    ; b = flags
        ld  a, (_serpent_tail_active)
        or  a, a
        jr  z, 11101$
        ld  a, (_serpent_head_index)
        cp  a, c
        jp  z, 11190$
    11101$:
        ld  a, (_cinder_pack_active)
        or  a, a
        jr  z, 11102$
        ld  a, (_cinder_boss_index)
        cp  a, c
        jp  z, 11190$
    11102$:
        ld  a, (hl)                 ; type
        cp  a, #4                   ; ENT_FX
        jr  z, 11110$
        cp  a, #1                   ; ENT_PROJECTILE
        jr  z, 11120$
        cp  a, #2                   ; ENT_ENEMY
        ret nz                      ; anything else: general path
        bit 2, b                    ; EF_ON_SCREEN
        jp  z, 11190$               ; asleep: not drawn
        push hl
        ld  de, #24                 ; ai_data[7] hit flash
        add hl, de
        ld  a, (hl)
        pop hl
        or  a, a
        ret nz
        push hl
        ld  hl, #_enemy_status_kind
        ld  e, c
        ld  d, #0
        add hl, de
        ld  a, (hl)
        pop hl
        or  a, a                    ; QSTATUS_NONE == 0
        ret nz
        ld  a, (_room_return_echo_kind)
        cp  a, #4
        jr  c, 11103$
        ld  a, (_room_encounter_target)
        cp  a, c
        ret z
    11103$:
        push hl
        ld  de, #17                 ; ai_data[0] = enemy id
        add hl, de
        ld  a, (hl)
        pop hl
        cp  a, #1                   ; Stone Sentinel
        ret z
        cp  a, #4                   ; Orc
        ret z
        cp  a, #6                   ; Bomber
        ret z
        cp  a, #8                   ; Warlock
        ret z
        cp  a, #14                  ; Cinder Maw
        ret z
        cp  a, #33                  ; Facet Ram
        ret z
        cp  a, #34                  ; Stage Reaper
        ret z
        sub a, #37                  ; Vault Hand / Bane Brute
        cp  a, #2
        ret c
    11110$:                         ; plain: prop = palette
        push hl
        ld  de, #13
        add hl, de
        ld  b, (hl)
        pop hl
        jr  11130$
    11120$:                         ; projectile
        bit 7, b                    ; EF_BOSS_PROJECTILE
        ret nz
        push hl
        ld  de, #23                 ; ai_data[6] aux
        add hl, de
        ld  a, (hl)
        cp  a, #0xF5                ; >= PROJ_AUX_HOOKSHOT
        jr  c, 11121$
        pop hl
        ret
    11121$:
        dec hl
        dec hl
        ld  a, (hl)                 ; ai_data[4] vis flips
        and a, #3
        swap a
        add a, a                    ; FLIP_X->S_FLIPX, FLIP_Y->S_FLIPY
        ld  b, a
        pop hl
        push hl
        ld  de, #13
        add hl, de
        ld  a, (hl)
        or  a, b
        ld  b, a                    ; b = prop
        pop hl
    11130$:                         ; emit, hl = e, b = prop
        ld  a, (_entity_oam_cap)
        ld  c, a
        ld  a, (_edr_oam)
        cp  a, c
        jp  nc, 11190$              ; OAM full: skip, as the C path
        inc hl
        inc hl
        inc hl                      ; +3 x
        ld  a, (_room_camera_x)
        ld  c, a
        ld  a, (hl)
        sub a, c
        add a, #8
        ld  d, a                    ; d = sx
        inc hl
        inc hl
        inc hl
        inc hl                      ; +7 y
        ld  a, (_room_camera_y)
        ld  c, a
        ld  a, (hl)
        sub a, c
        add a, #16
        ld  e, a                    ; e = sy
        inc hl
        inc hl
        inc hl
        inc hl
        inc hl                      ; +12 tile
        ld  c, (hl)
        ld  a, (_edr_oam)
        add a, a
        add a, a
        ld  l, a
        ld  h, #0
        push de
        ld  de, #_shadow_OAM
        add hl, de
        pop de
        ld  a, e
        ld  (hl+), a
        ld  a, d
        ld  (hl+), a
        ld  a, c
        ld  (hl+), a
        ld  (hl), b
        ld  hl, #_edr_oam
        inc (hl)
    11190$:                         ; next
        ld  hl, #_edr_i
        inc (hl)
        jp  11100$
    __endasm;
}
