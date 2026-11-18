// Secret merchants: one hidden Veil Trader vault per dungeon stage and three
// hidden cave merchants per Riftwild region, all reached through a concealed
// Zelda 1 style mouth (pushed rock, blasted face, walk-into thicket).
// See docs/superpowers/specs/2026-11-16-secret-merchants.md.
#ifndef QUINTRA_GAME_SECRET_MERCHANT_H
#define QUINTRA_GAME_SECRET_MERCHANT_H

#include <gb/gb.h>
#include "core/types.h"

// run_state.secret_shop (dungeon Veil stall; cleared when a dungeon begins).
#define SECRET_SHOP_B_BOUGHT 0x01u
#define SECRET_SHOP_C_BOUGHT 0x02u
#define SECRET_SHOP_MOUTH    0x04u
#define SECRET_SHOP_CHIMED   0x08u
#define SECRET_SHOP_ARMED    0x10u
#define SECRET_SHOP_FOUND    0x80u

// run_state.veil_charms (run-long): bits 0..8 Veil signatures by stage,
// bits 9..11 region Wild charms. Bit 15 records that Crimson Pact's +1 ATK
// is currently applied to player.atk (so a suspend never banks the bonus).
#define VEIL_CHARM_BIT(i)      ((u16)(1u << (i)))
#define VEIL_CAVE_LIGHT        0
#define VEIL_HONEYCOMB         1
#define VEIL_CINDER_VEIL       2
#define VEIL_RIME_SKATES       3
#define VEIL_FILTER_MASK       4
#define VEIL_GLOAM_LAMP        5
#define VEIL_SUN_SEAL          6
#define VEIL_CRIMSON_PACT      7
#define VEIL_LAST_LIGHT        8
#define VEIL_WAYFARER_BELL     9
#define VEIL_CACHE_LURE        10
#define VEIL_HOLLOW_WICK       11
#define VEIL_CRIMSON_APPLIED   0x8000u
#define VEIL_HAS(i) (run_state.veil_charms & VEIL_CHARM_BIT(i))

// run_state.rift_caves (current Riftwild region only).
#define RIFT_CAVE_FOUND(i)  ((u32)1u << (i))
#define RIFT_CAVE_MOUTH(i)  ((u32)1u << (3u + (i)))
#define RIFT_CAVE_CHIMED(i) ((u32)1u << (6u + (i)))
#define RIFT_CAVE_B(i)      ((u32)1u << (9u + (i)))
#define RIFT_CAVE_C(i)      ((u32)1u << (12u + (i)))
#define RIFT_CAVE_ARMED     ((u32)1u << 15)
#define RIFT_CAVE_FROM_SHIFT 16

#define SECRET_CAVE_COUNT        3
#define SECRET_CAVE_SCREEN_BASE  48
#define SECRET_CAVE_TELL_X       16
#define SECRET_CAVE_TELL_Y       13
// Concealment kinds (shared by Veil tells and Riftwild caves).
#define SECRET_KIND_STONE   0   // pushed rock / cairn
#define SECRET_KIND_BLAST   1   // blasted face (bomb, Morningstar, Rift Bomb)
#define SECRET_KIND_THICKET 2   // walk into the curtain

// WARE_SECRET ai_data[3] codes.
#define SM_TONIC_VEIL   0   // 0..8: stage tonic
#define SM_TONIC_RIFT   9
#define SM_BOTTLE_AEGIS 10
#define SM_BOTTLE_MEND  11
#define SM_BOTTLE_LIMIT 12
#define SM_BOTTLE_SURGE 13  // Grand Surge stand-in for unshipped bottles
#define SM_CHARM        14  // 14..25: veil_charms bit (code - 14)
#define SM_BOMB_BAG     26
#define SM_RIFT_BOMB    27
#define SM_ECHO_CHIME   28
#define SM_REARM_WELL   29
#define SM_CODE_COUNT   30

extern u8 secret_merchant_host_here;
extern u8 secret_merchant_armed;

// Local cell of this stage's Veil host, or 0xFF when the stage has none.
u8 secret_merchant_host_cell(void) BANKED;
// Concealment kind of this stage's Veil tell.
u8 secret_merchant_host_kind(void) BANKED;
// Every room entry (puzzle_prepare_room): bottle uncork, charm glints.
void secret_merchant_room_ready(void) BANKED;
// puzzle_prepare_room on an ordinary cell: 1 when this is the Veil host
// (its tell or open mouth is authored and ordinary secrets are skipped).
u8 secret_merchant_prepare_host(void) BANKED;
// procgen's secret overlay: 1 when it built the Veil stall instead.
u8 secret_merchant_build_stall(void) BANKED;
// PICKUP_SHOP contact on a WARE_SECRET shelf.
void secret_merchant_touch(u8 idx) BANKED;
// Keeper catalog line for a WARE_SECRET shelf (console text, NONBANKED out).
void secret_merchant_write_effect(u8 code) BANKED;
// Per frame while secret_merchant_armed.
void secret_merchant_tick(void) BANKED;
// Echo Chime in a dungeon room: 1 when it answered the Veil tell.
u8 secret_merchant_chime(void) BANKED;
// Dungeon Compass: host cell when found (bit 7 = dim, chimed only), else 0xFF.
u8 secret_merchant_map_cell(void) BANKED;
// Lethal hit after Phoenix declined: Last Light, once per run.
u8 secret_merchant_last_light(void) BANKED;
// Status about to land on the hero: 1 when a charm blocks it.
u8 secret_merchant_block_status(u8 kind) BANKED;

// Riftwild cave merchants.
u8 secret_cave_field_index(u8 field) BANKED;
u8 secret_cave_kind(u8 cave) BANKED;
u8 secret_cave_stamp_field(void) BANKED;
u8 secret_cave_strike(u8 tx, u8 ty) BANKED;
void secret_cave_burst(u8 tx, u8 ty) BANKED;
u8 secret_cave_portal(u8 tx, u8 ty) BANKED;
void secret_cave_build_room(void) BANKED;
u8 secret_cave_chime(void) BANKED;
u8 secret_cave_map_icon(u8 cell, u8 icon) BANKED;

#endif
