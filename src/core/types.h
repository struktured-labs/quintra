// Quintra core types — common typedefs, fixed-point math, ID newtypes
#ifndef QUINTRA_CORE_TYPES_H
#define QUINTRA_CORE_TYPES_H

#include <stdint.h>

typedef uint8_t  u8;
typedef int8_t   i8;
typedef uint16_t u16;
typedef int16_t  i16;
typedef uint32_t u32;
typedef int32_t  i32;

// Plain pixel-position type for world coordinates (player + entities).
// Avoids fix8 SDCC arithmetic quirks for positions that don't need
// sub-pixel motion. Rooms are <=160 px wide, well within i16 range.
typedef i16 ppos_t;

// Legacy API spelling retained while callers migrate. Entity movement has
// always been whole-pixel, so these are deliberately plain signed pixels—not
// costly 32-bit 8.8 values. Keeping the wrappers makes the semantic change
// local and prevents a noisy content-callsite rewrite.
typedef ppos_t fix8_t;
#define FIX8(n)            ((fix8_t)(n))
#define FIX8_TO_INT(f)     ((i16)(f))

// Typed IDs — defended at codegen time, opaque at runtime
typedef u8  class_id_t;
typedef u16 item_id_t;
typedef u8  enemy_id_t;
typedef u8  biome_id_t;
typedef u8  boss_id_t;
typedef u16 room_tpl_id_t;
typedef u8  palette_ref_t;
typedef u8  sprite_ref_t;
typedef u8  tileset_ref_t;
typedef u16 tilemap_id_t;
typedef u8  music_ref_t;
typedef u8  drop_table_id_t;
typedef u8  perk_id_t;
typedef u8  ai_script_id_t;
typedef u8  projectile_kind_t;
typedef u8  status_id_t;
typedef u8  screen_id_t;
typedef u8  entity_type_t;

// Sentinels
#define ID_NONE_U8   ((u8)0xFF)
#define ID_NONE_U16  ((u16)0xFFFF)

#endif
