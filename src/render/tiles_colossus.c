#pragma bank 5
#include <gb/gb.h>

#include "core/types.h"
#include "game/room.h"
#include "render/tiles.h"

// Screen-scale boss BG art lives in the roomy specialist bank rather than the
// shared tile atlas bank. The nine projected bosses never coexist in VRAM,
// so their projections share nine tile IDs while retaining distinct
// silhouettes.
// This keeps the HUD and the GBC's 40-object budget untouched.
static const u8 bgt_crystal_void[16] = {
    0x18,0x00, 0x3C,0x18, 0x66,0x3C, 0xC3,0x66,
    0x81,0x7E, 0xC3,0x66, 0x66,0x3C, 0x3C,0x18
};
static const u8 bgt_crystal_scale[16] = {
    0x18,0x00, 0x3C,0x18, 0x7E,0x3C, 0xDB,0x66,
    0xFF,0x7E, 0x7E,0x3C, 0x3C,0x18, 0x18,0x00
};
static const u8 bgt_crystal_edge_l[16] = {
    0x01,0x00, 0x03,0x01, 0x07,0x03, 0x0F,0x07,
    0x1F,0x0F, 0x3F,0x1F, 0x7F,0x3F, 0xFF,0x7F
};
static const u8 bgt_crystal_edge_r[16] = {
    0x80,0x00, 0xC0,0x80, 0xE0,0xC0, 0xF0,0xE0,
    0xF8,0xF0, 0xFC,0xF8, 0xFE,0xFC, 0xFF,0xFE
};
static const u8 bgt_crystal_eye[16] = {
    0x00,0x00, 0x7E,0x00, 0xFF,0x7E, 0xBD,0xC3,
    0xDB,0xE7, 0xFF,0x7E, 0x7E,0x00, 0x00,0x00
};
static const u8 bgt_crystal_fang[16] = {
    0x18,0x00, 0x3C,0x18, 0x7E,0x3C, 0xFF,0x7E,
    0x7E,0x3C, 0x3C,0x18, 0x18,0x00, 0x00,0x00
};
static const u8 bgt_crystal_rune[16] = {
    0x24,0x00, 0x5A,0x24, 0xA5,0x5A, 0x5A,0xA5,
    0xA5,0x5A, 0x5A,0x24, 0x24,0x18, 0x18,0x00
};
static const u8 bgt_crystal_maw[16] = {
    0x7E,0x00, 0xC3,0x7E, 0xBD,0xC3, 0xA5,0xDB,
    0xBD,0xC3, 0xC3,0x7E, 0x7E,0x00, 0x3C,0x00
};
static const u8 bgt_crystal_horn[16] = {
    0x08,0x08, 0x1C,0x14, 0x3E,0x2A, 0x7F,0x55,
    0xFE,0xAA, 0x7C,0xD4, 0x38,0x68, 0x10,0x30
};

// Verdant Hollow's storm coil. The mobile 32x32 OBJ remains the serpent's
// vulnerable head; this huge loop is its body and charged wake. A two-frame
// rune makes electricity travel through the coil without spending more OAM.
static const u8 bgt_serpent_void[16] = {
    0x00,0x00, 0x18,0x00, 0x24,0x18, 0x42,0x3C,
    0x24,0x18, 0x18,0x00, 0x24,0x18, 0x00,0x00
};
static const u8 bgt_serpent_scale[16] = {
    0x42,0x00, 0xA5,0x42, 0x5A,0xA5, 0xA5,0x5A,
    0x5A,0xA5, 0xA5,0x42, 0x42,0x24, 0x24,0x00
};
static const u8 bgt_serpent_edge_l[16] = {
    0x0F,0x00, 0x1F,0x0F, 0x3B,0x1F, 0x77,0x3B,
    0xEE,0x76, 0xDC,0xF8, 0xB8,0xF0, 0x70,0xE0
};
static const u8 bgt_serpent_edge_r[16] = {
    0xF0,0x00, 0xF8,0xF0, 0xDC,0xF8, 0xEE,0xDC,
    0x77,0x6E, 0x3B,0x1F, 0x1D,0x0F, 0x0E,0x07
};
static const u8 bgt_serpent_eye[16] = {
    0x00,0x00, 0x24,0x00, 0x5A,0x24, 0xA5,0x5A,
    0x5A,0xA5, 0x24,0x5A, 0x18,0x24, 0x00,0x18
};
static const u8 bgt_serpent_fang[16] = {
    0x10,0x00, 0x38,0x10, 0x7C,0x38, 0xFE,0x7C,
    0x7C,0x38, 0x38,0x10, 0x10,0x00, 0x00,0x00
};
static const u8 bgt_serpent_rune_a[16] = {
    0x08,0x00, 0x1C,0x08, 0x3E,0x1C, 0x7C,0x38,
    0x38,0x70, 0x10,0x38, 0x38,0x10, 0x10,0x00
};
static const u8 bgt_serpent_rune_b[16] = {
    0x10,0x00, 0x38,0x10, 0x70,0x38, 0x38,0x70,
    0x7C,0x38, 0x3E,0x1C, 0x1C,0x08, 0x08,0x00
};
static const u8 bgt_serpent_maw[16] = {
    0x3C,0x00, 0x7E,0x3C, 0xDB,0x66, 0xA5,0x7E,
    0xDB,0x66, 0x7E,0x3C, 0x3C,0x18, 0x18,0x00
};
static const u8 bgt_serpent_horn[16] = {
    0x80,0x80, 0xC0,0x40, 0xE0,0xA0, 0x70,0xD0,
    0x38,0x68, 0x1C,0x34, 0x0E,0x1A, 0x07,0x0D
};

// Ember Depths' furnace-beast. The open/closed eye and maw frames let the
// projected body follow the existing breath/lunge/recovery state machine
// without moving collision or vulnerability away from the OBJ core.
static const u8 bgt_cinder_void[16] = {
    0x00,0x00, 0x24,0x00, 0x5A,0x24, 0xA5,0x5A,
    0x42,0x3C, 0x99,0x66, 0x24,0x18, 0x00,0x00
};
static const u8 bgt_cinder_scale[16] = {
    0x81,0x00, 0xC3,0x81, 0xA5,0xC3, 0x5A,0x3C,
    0xA5,0x5A, 0xC3,0x81, 0x66,0x3C, 0x3C,0x18
};
static const u8 bgt_cinder_edge_l[16] = {
    0x07,0x00, 0x0F,0x07, 0x1E,0x0F, 0x3D,0x1E,
    0x7A,0x3C, 0xF5,0x7A, 0xEA,0xF4, 0xD0,0xE0
};
static const u8 bgt_cinder_edge_r[16] = {
    0xE0,0x00, 0xF0,0xE0, 0x78,0xF0, 0xBC,0x78,
    0x5E,0x3C, 0xAF,0x5E, 0x57,0x2F, 0x0B,0x07
};
static const u8 bgt_cinder_eye_open[16] = {
    0x00,0x00, 0x7E,0x00, 0xFF,0x7E, 0xC3,0xBD,
    0x99,0xE7, 0xFF,0x7E, 0x7E,0x00, 0x00,0x00
};
static const u8 bgt_cinder_eye_closed[16] = {
    0x00,0x00, 0x00,0x00, 0x66,0x00, 0xFF,0x66,
    0x7E,0x3C, 0x18,0x00, 0x00,0x00, 0x00,0x00
};
static const u8 bgt_cinder_fang[16] = {
    0xC3,0x00, 0x66,0xC3, 0x3C,0x66, 0x18,0x3C,
    0x3C,0x18, 0x66,0x3C, 0x42,0x24, 0x00,0x00
};
static const u8 bgt_cinder_rune[16] = {
    0x18,0x00, 0x5A,0x18, 0xBD,0x5A, 0x7E,0xBD,
    0xDB,0x66, 0x7E,0x3C, 0x5A,0x24, 0x18,0x00
};
static const u8 bgt_cinder_maw_open[16] = {
    0x7E,0x00, 0xFF,0x7E, 0x81,0xFF, 0xDB,0xA5,
    0xA5,0xDB, 0xDB,0xA5, 0x81,0xFF, 0x7E,0x00
};
static const u8 bgt_cinder_maw_closed[16] = {
    0x00,0x00, 0x00,0x00, 0x7E,0x00, 0xFF,0x7E,
    0xBD,0xC3, 0x7E,0x3C, 0x00,0x00, 0x00,0x00
};
static const u8 bgt_cinder_horn[16] = {
    0x10,0x10, 0x38,0x28, 0x7C,0x54, 0xFE,0xAA,
    0x7F,0x55, 0x3E,0x2A, 0x1C,0x14, 0x08,0x08
};

// Frost Vault's web-spider. The hollow body is a projection across its own
// charged web; the original blinking OBJ remains the only physical weak point.
static const u8 bgt_spider_void[16] = {
    0x81,0x00, 0x42,0x81, 0x24,0x42, 0x18,0x24,
    0x24,0x18, 0x42,0x24, 0x81,0x42, 0x00,0x81
};
static const u8 bgt_spider_scale[16] = {
    0x3C,0x00, 0x7E,0x3C, 0xDB,0x66, 0xA5,0x7E,
    0xDB,0x66, 0xA5,0x5A, 0x66,0x3C, 0x3C,0x18
};
static const u8 bgt_spider_edge_l[16] = {
    0x01,0x00, 0x03,0x01, 0x07,0x03, 0x0E,0x07,
    0x1C,0x0E, 0x38,0x1C, 0x70,0x38, 0xE0,0x70
};
static const u8 bgt_spider_edge_r[16] = {
    0x80,0x00, 0xC0,0x80, 0xE0,0xC0, 0x70,0xE0,
    0x38,0x70, 0x1C,0x38, 0x0E,0x1C, 0x07,0x0E
};
static const u8 bgt_spider_eye_open[16] = {
    0x00,0x00, 0x66,0x00, 0xFF,0x66, 0x99,0xE7,
    0xA5,0xDB, 0xFF,0x7E, 0x66,0x00, 0x00,0x00
};
static const u8 bgt_spider_eye_closed[16] = {
    0x00,0x00, 0x00,0x00, 0x24,0x00, 0x7E,0x24,
    0xFF,0x7E, 0x24,0x18, 0x00,0x00, 0x00,0x00
};
static const u8 bgt_spider_fang[16] = {
    0x42,0x00, 0xA5,0x42, 0x5A,0xA5, 0x3C,0x5A,
    0x18,0x3C, 0x18,0x00, 0x24,0x18, 0x00,0x00
};
static const u8 bgt_spider_web_a[16] = {
    0x81,0x00, 0x42,0x81, 0x24,0x42, 0x18,0x24,
    0x18,0x24, 0x24,0x42, 0x42,0x81, 0x81,0x00
};
static const u8 bgt_spider_web_b[16] = {
    0x18,0x00, 0x24,0x18, 0x42,0x24, 0x81,0x42,
    0x42,0x81, 0x24,0x42, 0x18,0x24, 0x00,0x18
};
static const u8 bgt_spider_maw[16] = {
    0x7E,0x00, 0xDB,0x7E, 0xA5,0xDB, 0x5A,0xA5,
    0xA5,0x5A, 0xDB,0xA5, 0x7E,0xDB, 0x3C,0x7E
};
static const u8 bgt_spider_horn[16] = {
    0x81,0x81, 0x42,0xC3, 0x24,0x66, 0x18,0x3C,
    0x3C,0x18, 0x66,0x24, 0xC3,0x42, 0x81,0x81
};

// Shadow Keep's Dusk Reaper: a widening spectral cloak around the existing
// teleporting OBJ weak point. Two void/eye frames make the robe phase rather
// than sit behind the fight as a static mural.
static const u8 bgt_reaper_void_a[16] = {
    0x00,0x00, 0x18,0x00, 0x3C,0x18, 0x66,0x3C,
    0xC3,0x66, 0x66,0x3C, 0x3C,0x18, 0x18,0x00
};
static const u8 bgt_reaper_void_b[16] = {
    0x18,0x00, 0x3C,0x18, 0x66,0x3C, 0xC3,0x66,
    0x66,0xC3, 0x3C,0x66, 0x18,0x3C, 0x00,0x18
};
static const u8 bgt_reaper_scale[16] = {
    0x81,0x00, 0x42,0x81, 0xA5,0x42, 0x5A,0xA5,
    0xA5,0x5A, 0x42,0xA5, 0x81,0x42, 0x42,0x00
};
static const u8 bgt_reaper_edge_l[16] = {
    0x01,0x00, 0x03,0x01, 0x07,0x03, 0x0F,0x07,
    0x1E,0x0F, 0x3C,0x1E, 0x78,0x3C, 0xF0,0x78
};
static const u8 bgt_reaper_edge_r[16] = {
    0x80,0x00, 0xC0,0x80, 0xE0,0xC0, 0xF0,0xE0,
    0x78,0xF0, 0x3C,0x78, 0x1E,0x3C, 0x0F,0x1E
};
static const u8 bgt_reaper_eye_open[16] = {
    0x00,0x00, 0x66,0x00, 0xFF,0x66, 0x99,0xE7,
    0x81,0xFF, 0xFF,0x7E, 0x66,0x00, 0x00,0x00
};
static const u8 bgt_reaper_eye_closed[16] = {
    0x00,0x00, 0x00,0x00, 0x24,0x00, 0x7E,0x24,
    0xFF,0x7E, 0x18,0x24, 0x00,0x18, 0x00,0x00
};
static const u8 bgt_reaper_fang[16] = {
    0x80,0x80, 0xC0,0x40, 0x60,0xA0, 0x30,0x50,
    0x18,0x28, 0x0C,0x14, 0x06,0x0A, 0x03,0x05
};
static const u8 bgt_reaper_rune[16] = {
    0x18,0x00, 0x3C,0x18, 0x7E,0x3C, 0xDB,0x66,
    0x7E,0xDB, 0x3C,0x66, 0x18,0x3C, 0x24,0x18
};
static const u8 bgt_reaper_maw[16] = {
    0x7E,0x00, 0xC3,0x7E, 0xBD,0xC3, 0x81,0xFF,
    0xA5,0xDB, 0xBD,0xC3, 0xC3,0x7E, 0x7E,0x00
};
static const u8 bgt_reaper_horn[16] = {
    0x18,0x18, 0x3C,0x24, 0x7E,0x42, 0xFF,0x81,
    0xE7,0xBD, 0xC3,0x66, 0x81,0x42, 0x00,0x81
};

static const u8 bgt_mire_void[16] = {
    0x00,0x00, 0x18,0x00, 0x24,0x18, 0x42,0x3C,
    0x81,0x7E, 0x42,0x3C, 0x24,0x18, 0x18,0x00
};
static const u8 bgt_mire_scale[16] = {
    0x18,0x00, 0x24,0x18, 0x5A,0x24, 0xA5,0x5A,
    0x81,0x7E, 0xA5,0x5A, 0x42,0x3C, 0x24,0x18
};
static const u8 bgt_mire_edge_l[16] = {
    0x07,0x00, 0x0F,0x07, 0x1F,0x0F, 0x3E,0x1F,
    0x7D,0x3E, 0xFA,0x7C, 0xF4,0xF8, 0xE0,0xF0
};
static const u8 bgt_mire_edge_r[16] = {
    0xE0,0x00, 0xF0,0xE0, 0xF8,0xF0, 0x7C,0xF8,
    0xBE,0x7C, 0x5F,0x3E, 0x2F,0x1F, 0x07,0x0F
};
static const u8 bgt_mire_eye[16] = {
    0x00,0x00, 0x3C,0x00, 0x7E,0x3C, 0xDB,0x66,
    0xA5,0x7E, 0x7E,0x3C, 0x3C,0x00, 0x00,0x00
};
static const u8 bgt_mire_fang[16] = {
    0x81,0x00, 0xC3,0x81, 0x66,0xC3, 0x3C,0x66,
    0x18,0x3C, 0x18,0x00, 0x24,0x18, 0x18,0x00
};
static const u8 bgt_mire_rune[16] = {
    0x00,0x00, 0x18,0x00, 0x24,0x18, 0x5A,0x24,
    0x5A,0x24, 0x24,0x18, 0x18,0x00, 0x00,0x00
};
static const u8 bgt_mire_maw[16] = {
    0x7E,0x00, 0xFF,0x7E, 0x81,0xFF, 0xBD,0xC3,
    0xA5,0xDB, 0xBD,0xC3, 0x81,0xFF, 0x7E,0x00
};
static const u8 bgt_mire_horn[16] = {
    0x08,0x08, 0x14,0x0C, 0x2A,0x1C, 0x55,0x3E,
    0xAA,0x7C, 0x54,0x38, 0x28,0x30, 0x10,0x20
};

// Bloodmoon's three-headed coil. Two head tiles trade open/closed art at
// runtime, making the projected creature participate in the staggered-stream
// rhythm instead of sitting behind the mobile OBJ weak point as wallpaper.
static const u8 bgt_hydra_void[16] = {
    0x0C,0x00, 0x1E,0x0C, 0x33,0x1E, 0x61,0x3F,
    0xC3,0x7E, 0x86,0x7C, 0xCC,0x78, 0x78,0x30
};
static const u8 bgt_hydra_scale[16] = {
    0x24,0x00, 0x5A,0x24, 0xA5,0x5A, 0x5A,0xA5,
    0xA5,0x5A, 0x42,0x3C, 0xA5,0x42, 0x5A,0x24
};
static const u8 bgt_hydra_edge_l[16] = {
    0x03,0x00, 0x07,0x03, 0x0E,0x07, 0x1D,0x0E,
    0x3A,0x1C, 0x75,0x3A, 0xEA,0x74, 0xD4,0xE8
};
static const u8 bgt_hydra_edge_r[16] = {
    0xC0,0x00, 0xE0,0xC0, 0x70,0xE0, 0xB8,0x70,
    0x5C,0x38, 0xAE,0x5C, 0x57,0x2E, 0x2B,0x17
};
static const u8 bgt_hydra_head_open[16] = {
    0x3C,0x00, 0x7E,0x3C, 0xDB,0x66, 0xA5,0x7E,
    0xFF,0x7E, 0xA5,0xDB, 0x5A,0x3C, 0x24,0x18
};
static const u8 bgt_hydra_head_closed[16] = {
    0x18,0x00, 0x3C,0x18, 0x66,0x3C, 0xFF,0x66,
    0x7E,0x3C, 0x3C,0x18, 0x18,0x00, 0x00,0x00
};
static const u8 bgt_hydra_fang[16] = {
    0x81,0x00, 0xC3,0x81, 0x66,0xC3, 0x3C,0x66,
    0x5A,0x3C, 0x24,0x18, 0x18,0x00, 0x00,0x00
};
static const u8 bgt_hydra_rune[16] = {
    0x66,0x00, 0xFF,0x66, 0x99,0x7E, 0x3C,0x99,
    0x7E,0x3C, 0x99,0x66, 0xFF,0x66, 0x66,0x00
};
static const u8 bgt_hydra_horn[16] = {
    0x42,0x42, 0xA5,0xE7, 0x5A,0xBD, 0x24,0x7E,
    0x18,0x3C, 0x24,0x18, 0x42,0x24, 0x81,0x42
};

// Golden Temple's awakened guardian is a monumental carved idol rather than
// another fleshy giant. Its crown, slab shoulders, and paired sun-runes fill
// the room while the original 32x32 OBJ remains the moving, vulnerable heart.
static const u8 bgt_golem_void[16] = {
    0xFF,0x00, 0x81,0x7E, 0xBD,0x42, 0xA5,0x5A,
    0xA5,0x5A, 0xBD,0x42, 0x81,0x7E, 0xFF,0x00
};
static const u8 bgt_golem_scale[16] = {
    0xFF,0x00, 0xC3,0x3C, 0x99,0x66, 0xBD,0x42,
    0xA5,0x5A, 0xBD,0x42, 0x99,0x66, 0xC3,0x3C
};
static const u8 bgt_golem_edge_l[16] = {
    0x0F,0x00, 0x1F,0x0F, 0x3F,0x1F, 0x7B,0x3F,
    0xF7,0x7B, 0xEF,0x77, 0xDF,0x6F, 0xBF,0x5F
};
static const u8 bgt_golem_edge_r[16] = {
    0xF0,0x00, 0xF8,0xF0, 0xFC,0xF8, 0xDE,0xFC,
    0xEF,0xDE, 0xF7,0xEE, 0xFB,0xF6, 0xFD,0xFA
};
static const u8 bgt_golem_eye_open[16] = {
    0x00,0x00, 0x7E,0x00, 0xFF,0x7E, 0xDB,0xA5,
    0xBD,0xC3, 0xFF,0x7E, 0x7E,0x00, 0x00,0x00
};
static const u8 bgt_golem_eye_closed[16] = {
    0x00,0x00, 0x00,0x00, 0x66,0x00, 0xFF,0x66,
    0x7E,0x3C, 0x18,0x00, 0x00,0x00, 0x00,0x00
};
static const u8 bgt_golem_fang[16] = {
    0xFF,0x00, 0x81,0x7E, 0xBD,0x42, 0x81,0x7E,
    0xBD,0x42, 0x81,0x7E, 0xFF,0x00, 0x7E,0x00
};
static const u8 bgt_golem_rune_bright[16] = {
    0x18,0x00, 0x5A,0x18, 0xBD,0x5A, 0x7E,0xBD,
    0xFF,0x7E, 0x7E,0xBD, 0xBD,0x5A, 0x5A,0x18
};
static const u8 bgt_golem_rune_dim[16] = {
    0x00,0x00, 0x18,0x00, 0x24,0x18, 0x5A,0x24,
    0x3C,0x5A, 0x24,0x18, 0x18,0x00, 0x00,0x00
};
static const u8 bgt_golem_maw[16] = {
    0xFF,0x00, 0x81,0x7E, 0xBD,0xC3, 0xA5,0xDB,
    0xBD,0xC3, 0xA5,0xDB, 0x81,0xFF, 0xFF,0x00
};
static const u8 bgt_golem_horn[16] = {
    0x18,0x18, 0x3C,0x24, 0x7E,0x42, 0xFF,0x81,
    0xDB,0xA5, 0xFF,0x81, 0x7E,0x42, 0x3C,0x24
};

static const u8 bgt_colossus_void[16] = {
    0x00,0x00, 0x30,0x00, 0x48,0x30, 0x54,0x38,
    0x2C,0x18, 0x12,0x0C, 0x0C,0x00, 0x00,0x00
};
static const u8 bgt_colossus_scale[16] = {
    0x3C,0x00, 0x42,0x3C, 0xBD,0x7E, 0x81,0x7E,
    0x7E,0x00, 0x24,0x00, 0x42,0x00, 0x81,0x00
};
static const u8 bgt_colossus_edge_l[16] = {
    0x03,0x00, 0x05,0x03, 0x0A,0x07, 0x15,0x0E,
    0x2A,0x1C, 0x54,0x38, 0xA8,0x70, 0x50,0xE0
};
static const u8 bgt_colossus_edge_r[16] = {
    0xC0,0x00, 0xA0,0xC0, 0x50,0xE0, 0xA8,0x70,
    0x54,0x38, 0x2A,0x1C, 0x15,0x0E, 0x0A,0x07
};
static const u8 bgt_colossus_eye_open[16] = {
    0x00,0x00, 0x7E,0x00, 0xBD,0x7E, 0xDB,0x66,
    0xBD,0x7E, 0x7E,0x00, 0x00,0x00, 0x00,0x00
};
static const u8 bgt_colossus_eye_closed[16] = {
    0x00,0x00, 0x00,0x00, 0x7E,0x00, 0xBD,0x7E,
    0x7E,0x00, 0x00,0x00, 0x00,0x00, 0x00,0x00
};
static const u8 bgt_colossus_fang[16] = {
    0x81,0x81, 0x42,0xC3, 0xA5,0x66, 0x5A,0x3C,
    0x24,0x18, 0x24,0x18, 0x18,0x00, 0x00,0x00
};
static const u8 bgt_colossus_rune[16] = {
    0x18,0x00, 0x3C,0x18, 0x66,0x3C, 0xDB,0x66,
    0xDB,0x66, 0x66,0x3C, 0x3C,0x18, 0x18,0x00
};
static const u8 bgt_colossus_maw[16] = {
    0xFF,0x00, 0x81,0x7E, 0x7E,0xFF, 0x81,0xFF,
    0xBD,0xC3, 0x7E,0xC3, 0xBD,0x7E, 0x7E,0x00
};
static const u8 bgt_colossus_horn[16] = {
    0x02,0x02, 0x04,0x06, 0x0A,0x0C, 0x14,0x18,
    0x28,0x30, 0x50,0x60, 0xA0,0xC0, 0x40,0x80
};

void tiles_load_colossus_bg(u8 stage) BANKED {
    u8 mire = (stage == 4);
    if (stage == 0) {
        set_bkg_data(BGT_COLOSSUS_VOID,   1, bgt_crystal_void);
        set_bkg_data(BGT_COLOSSUS_SCALE,  1, bgt_crystal_scale);
        set_bkg_data(BGT_COLOSSUS_EDGE_L, 1, bgt_crystal_edge_l);
        set_bkg_data(BGT_COLOSSUS_EDGE_R, 1, bgt_crystal_edge_r);
        set_bkg_data(BGT_COLOSSUS_EYE,    1, bgt_crystal_eye);
        set_bkg_data(BGT_COLOSSUS_FANG,   1, bgt_crystal_fang);
        set_bkg_data(BGT_COLOSSUS_RUNE,   1, bgt_crystal_rune);
        set_bkg_data(BGT_COLOSSUS_MAW,    1, bgt_crystal_maw);
        set_bkg_data(BGT_COLOSSUS_HORN,   1, bgt_crystal_horn);
        return;
    }
    if (stage == 1) {
        set_bkg_data(BGT_COLOSSUS_VOID,   1, bgt_serpent_void);
        set_bkg_data(BGT_COLOSSUS_SCALE,  1, bgt_serpent_scale);
        set_bkg_data(BGT_COLOSSUS_EDGE_L, 1, bgt_serpent_edge_l);
        set_bkg_data(BGT_COLOSSUS_EDGE_R, 1, bgt_serpent_edge_r);
        set_bkg_data(BGT_COLOSSUS_EYE,    1, bgt_serpent_eye);
        set_bkg_data(BGT_COLOSSUS_FANG,   1, bgt_serpent_fang);
        set_bkg_data(BGT_COLOSSUS_RUNE,   1, bgt_serpent_rune_a);
        set_bkg_data(BGT_COLOSSUS_MAW,    1, bgt_serpent_maw);
        set_bkg_data(BGT_COLOSSUS_HORN,   1, bgt_serpent_horn);
        return;
    }
    if (stage == 2) {
        set_bkg_data(BGT_COLOSSUS_VOID,   1, bgt_cinder_void);
        set_bkg_data(BGT_COLOSSUS_SCALE,  1, bgt_cinder_scale);
        set_bkg_data(BGT_COLOSSUS_EDGE_L, 1, bgt_cinder_edge_l);
        set_bkg_data(BGT_COLOSSUS_EDGE_R, 1, bgt_cinder_edge_r);
        set_bkg_data(BGT_COLOSSUS_EYE,    1, bgt_cinder_eye_open);
        set_bkg_data(BGT_COLOSSUS_FANG,   1, bgt_cinder_fang);
        set_bkg_data(BGT_COLOSSUS_RUNE,   1, bgt_cinder_rune);
        set_bkg_data(BGT_COLOSSUS_MAW,    1, bgt_cinder_maw_open);
        set_bkg_data(BGT_COLOSSUS_HORN,   1, bgt_cinder_horn);
        return;
    }
    if (stage == 3) {
        set_bkg_data(BGT_COLOSSUS_VOID,   1, bgt_spider_void);
        set_bkg_data(BGT_COLOSSUS_SCALE,  1, bgt_spider_scale);
        set_bkg_data(BGT_COLOSSUS_EDGE_L, 1, bgt_spider_edge_l);
        set_bkg_data(BGT_COLOSSUS_EDGE_R, 1, bgt_spider_edge_r);
        set_bkg_data(BGT_COLOSSUS_EYE,    1, bgt_spider_eye_open);
        set_bkg_data(BGT_COLOSSUS_FANG,   1, bgt_spider_fang);
        set_bkg_data(BGT_COLOSSUS_RUNE,   1, bgt_spider_web_a);
        set_bkg_data(BGT_COLOSSUS_MAW,    1, bgt_spider_maw);
        set_bkg_data(BGT_COLOSSUS_HORN,   1, bgt_spider_horn);
        return;
    }
    if (stage == 5) {
        set_bkg_data(BGT_COLOSSUS_VOID,   1, bgt_reaper_void_a);
        set_bkg_data(BGT_COLOSSUS_SCALE,  1, bgt_reaper_scale);
        set_bkg_data(BGT_COLOSSUS_EDGE_L, 1, bgt_reaper_edge_l);
        set_bkg_data(BGT_COLOSSUS_EDGE_R, 1, bgt_reaper_edge_r);
        set_bkg_data(BGT_COLOSSUS_EYE,    1, bgt_reaper_eye_open);
        set_bkg_data(BGT_COLOSSUS_FANG,   1, bgt_reaper_fang);
        set_bkg_data(BGT_COLOSSUS_RUNE,   1, bgt_reaper_rune);
        set_bkg_data(BGT_COLOSSUS_MAW,    1, bgt_reaper_maw);
        set_bkg_data(BGT_COLOSSUS_HORN,   1, bgt_reaper_horn);
        return;
    }
    if (stage == 6) {
        set_bkg_data(BGT_COLOSSUS_VOID,   1, bgt_golem_void);
        set_bkg_data(BGT_COLOSSUS_SCALE,  1, bgt_golem_scale);
        set_bkg_data(BGT_COLOSSUS_EDGE_L, 1, bgt_golem_edge_l);
        set_bkg_data(BGT_COLOSSUS_EDGE_R, 1, bgt_golem_edge_r);
        set_bkg_data(BGT_COLOSSUS_EYE,    1, bgt_golem_eye_open);
        set_bkg_data(BGT_COLOSSUS_FANG,   1, bgt_golem_fang);
        set_bkg_data(BGT_COLOSSUS_RUNE,   1, bgt_golem_rune_bright);
        set_bkg_data(BGT_COLOSSUS_MAW,    1, bgt_golem_maw);
        set_bkg_data(BGT_COLOSSUS_HORN,   1, bgt_golem_horn);
        return;
    }
    if (stage == 7) {
        set_bkg_data(BGT_COLOSSUS_VOID,   1, bgt_hydra_void);
        set_bkg_data(BGT_COLOSSUS_SCALE,  1, bgt_hydra_scale);
        set_bkg_data(BGT_COLOSSUS_EDGE_L, 1, bgt_hydra_edge_l);
        set_bkg_data(BGT_COLOSSUS_EDGE_R, 1, bgt_hydra_edge_r);
        set_bkg_data(BGT_COLOSSUS_EYE,    1, bgt_hydra_head_open);
        set_bkg_data(BGT_COLOSSUS_FANG,   1, bgt_hydra_fang);
        set_bkg_data(BGT_COLOSSUS_RUNE,   1, bgt_hydra_rune);
        set_bkg_data(BGT_COLOSSUS_MAW,    1, bgt_hydra_head_closed);
        set_bkg_data(BGT_COLOSSUS_HORN,   1, bgt_hydra_horn);
        return;
    }
    set_bkg_data(BGT_COLOSSUS_VOID,   1, mire ? bgt_mire_void : bgt_colossus_void);
    set_bkg_data(BGT_COLOSSUS_SCALE,  1, mire ? bgt_mire_scale : bgt_colossus_scale);
    set_bkg_data(BGT_COLOSSUS_EDGE_L, 1, mire ? bgt_mire_edge_l : bgt_colossus_edge_l);
    set_bkg_data(BGT_COLOSSUS_EDGE_R, 1, mire ? bgt_mire_edge_r : bgt_colossus_edge_r);
    set_bkg_data(BGT_COLOSSUS_EYE,    1, mire ? bgt_mire_eye : bgt_colossus_eye_open);
    set_bkg_data(BGT_COLOSSUS_FANG,   1, mire ? bgt_mire_fang : bgt_colossus_fang);
    set_bkg_data(BGT_COLOSSUS_RUNE,   1, mire ? bgt_mire_rune : bgt_colossus_rune);
    set_bkg_data(BGT_COLOSSUS_MAW,    1, mire ? bgt_mire_maw : bgt_colossus_maw);
    set_bkg_data(BGT_COLOSSUS_HORN,   1, mire ? bgt_mire_horn : bgt_colossus_horn);
}

void tiles_paint_serpent_projection(void) BANKED {
    // Two hollow waist rows keep this a readable coil rather than another
    // filled face silhouette. The 14x8 outer span still dominates the arena.
    static const u8 lefts[8]  = { 7,5,3,3,3,3,5,7 };
    static const u8 widths[8] = { 6,10,14,14,14,14,10,6 };
    u8 y, x;
    for (y = 0; y < 8; ++y) {
        u8 left = lefts[y], width = widths[y];
        for (x = 0; x < width; ++x) {
            u8 hollow = (y == 3 || y == 5) && x >= 6 && x <= 7;
            u8 tile = BGT_COLOSSUS_SCALE;
            if (hollow) continue;
            if (x == 0) tile = BGT_COLOSSUS_EDGE_L;
            else if (x == width - 1) tile = BGT_COLOSSUS_EDGE_R;
            else if ((y == 0 || y == 7) && (x == 1 || x == width - 2))
                tile = BGT_COLOSSUS_HORN;
            else if (((u8)(x + y) & 3) == 0)
                tile = BGT_COLOSSUS_RUNE;
            else if (y == 2 && (x == 3 || x == width - 4))
                tile = BGT_COLOSSUS_EYE;
            else if (y >= 4 && ((u8)(x + y) & 1))
                tile = BGT_COLOSSUS_VOID;
            room_tilemap[y + 4][left + x] = tile;
        }
    }
}

void tiles_paint_spider_projection(void) BANKED {
    static const u8 widths[8] = { 10,14,14,14,14,14,12,8 };
    u8 y, x;
    for (y = 0; y < 8; ++y) {
        u8 width = widths[y];
        u8 left = (u8)(10 - (width >> 1));
        for (x = 0; x < width; ++x) {
            u8 hollow = (y == 3 && x >= 5 && x <= 8)
                || (y == 5 && x >= 6 && x <= 7);
            u8 tile = BGT_COLOSSUS_SCALE;
            if (hollow) continue;
            if (x == 0) tile = BGT_COLOSSUS_EDGE_L;
            else if (x == width - 1) tile = BGT_COLOSSUS_EDGE_R;
            else if ((y == 0 || y == 7) && (x == 1 || x == width - 2))
                tile = BGT_COLOSSUS_HORN;
            else if (y == 2 && (x == 3 || x == width - 4))
                tile = BGT_COLOSSUS_EYE;
            else if (y == 4 && x >= (u8)((width >> 1) - 2)
                && x <= (u8)((width >> 1) + 1))
                tile = BGT_COLOSSUS_MAW;
            else if (y == 5 && (x == 4 || x == width - 5))
                tile = BGT_COLOSSUS_FANG;
            else if (((u8)(x + y) & 2) == 0)
                tile = BGT_COLOSSUS_RUNE;
            else if (y >= 4) tile = BGT_COLOSSUS_VOID;
            room_tilemap[y + 4][left + x] = tile;
        }
    }
}

void tiles_paint_reaper_projection(void) BANKED {
    static const u8 widths[8] = { 8,10,12,14,14,14,14,14 };
    u8 y, x;
    for (y = 0; y < 8; ++y) {
        u8 width = widths[y];
        u8 left = (u8)(10 - (width >> 1));
        for (x = 0; x < width; ++x) {
            u8 tattered = y == 7 && (x == 3 || x == 5 || x == 8 || x == 10);
            u8 tile = BGT_COLOSSUS_SCALE;
            if (tattered) continue;
            if (x == 0) tile = BGT_COLOSSUS_EDGE_L;
            else if (x == width - 1) tile = BGT_COLOSSUS_EDGE_R;
            else if (y == 0 && (x == 1 || x == width - 2))
                tile = BGT_COLOSSUS_HORN;
            else if (y == 2 && (x == 3 || x == width - 4))
                tile = BGT_COLOSSUS_EYE;
            else if (y == 3 && x >= (u8)((width >> 1) - 2)
                && x <= (u8)((width >> 1) + 1))
                tile = BGT_COLOSSUS_MAW;
            else if (y == 4 && (x == 3 || x == width - 4))
                tile = BGT_COLOSSUS_FANG;
            else if (y >= 5 && ((u8)(x + y) & 1))
                tile = BGT_COLOSSUS_VOID;
            else if (((u8)(x + y) & 3) == 0)
                tile = BGT_COLOSSUS_RUNE;
            room_tilemap[y + 4][left + x] = tile;
        }
    }
}

void tiles_paint_cinder_projection(void) BANKED {
    static const u8 widths[8] = { 8,12,14,14,14,14,12,8 };
    u8 y, x;
    for (y = 0; y < 8; ++y) {
        u8 width = widths[y];
        u8 left = (u8)(10 - (width >> 1));
        for (x = 0; x < width; ++x) {
            u8 tile = BGT_COLOSSUS_SCALE;
            if (x == 0) tile = BGT_COLOSSUS_EDGE_L;
            else if (x == width - 1) tile = BGT_COLOSSUS_EDGE_R;
            else if (y == 0 && (x == 1 || x == width - 2))
                tile = BGT_COLOSSUS_HORN;
            else if (y == 2 && (x == 3 || x == width - 4))
                tile = BGT_COLOSSUS_EYE;
            else if ((y == 3 || y == 4)
                && x >= (u8)((width >> 1) - 2)
                && x <= (u8)((width >> 1) + 1))
                tile = BGT_COLOSSUS_MAW;
            else if (y == 5 && (x == (u8)((width >> 1) - 2)
                || x == (u8)((width >> 1) + 1)))
                tile = BGT_COLOSSUS_FANG;
            else if (y >= 5 && ((u8)(x + y) & 1))
                tile = BGT_COLOSSUS_VOID;
            else if (((u8)(x + y) & 3) == 0)
                tile = BGT_COLOSSUS_RUNE;
            room_tilemap[y + 4][left + x] = tile;
        }
    }
}

void tiles_paint_hydra_projection(void) BANKED {
    static const u8 widths[8] = { 10,14,14,14,14,14,12,8 };
    u8 y, x;
    for (y = 0; y < 8; ++y) {
        u8 width = widths[y];
        u8 left = (u8)(10 - (width >> 1));
        for (x = 0; x < width; ++x) {
            u8 gx = (u8)(left + x);
            u8 tile = BGT_COLOSSUS_SCALE;
            if (x == 0) tile = BGT_COLOSSUS_EDGE_L;
            else if (x == width - 1) tile = BGT_COLOSSUS_EDGE_R;
            // Three heads at x=6/9/13. The side pair and centre use two
            // shared tile IDs so their breathing volley posture can alternate.
            else if (y == 0 && (gx == 6 || gx == 13)) tile = BGT_COLOSSUS_EYE;
            else if (y == 0 && gx == 9) tile = BGT_COLOSSUS_MAW;
            else if (y == 1 && (gx == 6 || gx == 9 || gx == 13))
                tile = BGT_COLOSSUS_HORN;
            else if (y == 2 && (gx == 6 || gx == 9 || gx == 13))
                tile = BGT_COLOSSUS_FANG;
            else if (y >= 5 && ((u8)(x + y) & 1)) tile = BGT_COLOSSUS_VOID;
            else if (((u8)(x + y) & 3) == 0) tile = BGT_COLOSSUS_RUNE;
            room_tilemap[y + 4][gx] = tile;
        }
    }
}

void tiles_paint_golem_projection(void) BANKED {
    // Nine rows form a 112x72 temple idol. The narrow crown and split feet
    // keep its silhouette distinct from the organic coils and cloaks.
    static const u8 widths[9] = { 6,10,14,14,14,14,14,12,10 };
    u8 y, x;
    for (y = 0; y < 9; ++y) {
        u8 width = widths[y];
        u8 left = (u8)(10 - (width >> 1));
        for (x = 0; x < width; ++x) {
            u8 gx = (u8)(left + x);
            u8 split_foot = y == 8 && (x == 4 || x == 5);
            u8 tile = BGT_COLOSSUS_SCALE;
            if (split_foot) continue;
            if (x == 0) tile = BGT_COLOSSUS_EDGE_L;
            else if (x == width - 1) tile = BGT_COLOSSUS_EDGE_R;
            else if (y == 0 && (x == 1 || x == width - 2))
                tile = BGT_COLOSSUS_HORN;
            else if (y == 2 && (x == 3 || x == width - 4))
                tile = BGT_COLOSSUS_EYE;
            else if (y == 3 && (x == 4 || x == width - 5))
                tile = BGT_COLOSSUS_RUNE;
            else if ((y == 4 || y == 5)
                && x >= (u8)((width >> 1) - 2)
                && x <= (u8)((width >> 1) + 1))
                tile = BGT_COLOSSUS_MAW;
            else if (y == 6 && (x == 2 || x == width - 3))
                tile = BGT_COLOSSUS_FANG;
            else if (y >= 6 && ((u8)(x + y) & 1))
                tile = BGT_COLOSSUS_VOID;
            room_tilemap[y + 3][gx] = tile;
        }
    }
}

void tiles_paint_crystal_projection(void) BANKED {
    static const u8 widths[9] = { 8,12,14,14,14,14,14,12,8 };
    u8 y, x;
    for (y = 0; y < 9; ++y) {
        u8 width = widths[y];
        u8 left = (u8)(10 - (width >> 1));
        for (x = 0; x < width; ++x) {
            u8 tile = BGT_COLOSSUS_SCALE;
            if (x == 0) tile = BGT_COLOSSUS_EDGE_L;
            else if (x == width - 1) tile = BGT_COLOSSUS_EDGE_R;
            else if (y == 0 && (x == 1 || x == width - 2)) tile = BGT_COLOSSUS_HORN;
            else if (y == 2 && (x == 3 || x == width - 4)) tile = BGT_COLOSSUS_EYE;
            else if (y == 4 && x >= (u8)((width >> 1) - 2)
                && x <= (u8)((width >> 1) + 1)) tile = BGT_COLOSSUS_MAW;
            else if (y >= 6 && ((u8)(x + y) & 2)) tile = BGT_COLOSSUS_VOID;
            else if (((u8)(x + y) & 3) == 0) tile = BGT_COLOSSUS_RUNE;
            room_tilemap[y + 3][left + x] = tile;
        }
    }
}

void tiles_paint_mire_projection(u8 expanded, u8 draw_vram) BANKED {
    static const u8 width_expanded[8] = { 8,10,12,12,12,12,10,8 };
    static const u8 width_contracted[6] = { 4,6,8,8,6,4 };
    u8 y, x;
    for (y = 4; y < 12; ++y)
        for (x = 4; x < 16; ++x)
            room_tilemap[y][x] = BGT_FLOOR;

    if (expanded) {
        for (y = 0; y < 8; ++y) {
            u8 width = width_expanded[y];
            u8 left = (u8)(10 - (width >> 1));
            for (x = 0; x < width; ++x) {
                u8 tile = BGT_COLOSSUS_SCALE;
                if (x == 0) tile = BGT_COLOSSUS_EDGE_L;
                else if (x == width - 1) tile = BGT_COLOSSUS_EDGE_R;
                else if (y == 2 && (x == 3 || x == width - 4)) tile = BGT_COLOSSUS_EYE;
                else if (y == 4 && x >= (u8)((width >> 1) - 1)
                    && x <= (u8)(width >> 1)) tile = BGT_COLOSSUS_MAW;
                else if (((u8)(x + y) & 3) == 0) tile = BGT_COLOSSUS_RUNE;
                room_tilemap[y + 4][left + x] = tile;
            }
        }
    } else {
        for (y = 0; y < 6; ++y) {
            u8 width = width_contracted[y];
            u8 left = (u8)(10 - (width >> 1));
            for (x = 0; x < width; ++x) {
                u8 tile = BGT_COLOSSUS_VOID;
                if (x == 0) tile = BGT_COLOSSUS_EDGE_L;
                else if (x == width - 1) tile = BGT_COLOSSUS_EDGE_R;
                else if (y == 2 && (x == 2 || x == width - 3)) tile = BGT_COLOSSUS_EYE;
                else if (y == 3 && x >= (u8)((width >> 1) - 1)
                    && x <= (u8)(width >> 1)) tile = BGT_COLOSSUS_MAW;
                room_tilemap[y + 5][left + x] = tile;
            }
        }
    }

    if (draw_vram) {
        u8 attrs[12];
        for (y = 4; y < 12; ++y) {
            for (x = 0; x < 12; ++x) {
                u8 tile = room_tilemap[y][x + 4];
                attrs[x] = (tile == BGT_COLOSSUS_EDGE_L
                    || tile == BGT_COLOSSUS_EDGE_R
                    || tile == BGT_COLOSSUS_SCALE
                    || tile == BGT_COLOSSUS_HORN) ? BGPAL_WALL
                    : (tile == BGT_COLOSSUS_EYE || tile == BGT_COLOSSUS_FANG)
                        ? BGPAL_CRACK
                        : (tile >= BGT_COLOSSUS_VOID && tile <= BGT_COLOSSUS_HORN)
                            ? BGPAL_CRYSTAL : BGPAL_FLOOR;
            }
            VBK_REG = 0; set_bkg_tiles(4, y, 12, 1, &room_tilemap[y][4]);
            VBK_REG = 1; set_bkg_tiles(4, y, 12, 1, attrs);
        }
        VBK_REG = 0;
    }
}

void tiles_paint_void_projection(void) BANKED {
    static const u8 body[10][16] = {
        { 0xFF,BGT_COLOSSUS_HORN,0xFF,0xFF,0xFF,0xFF,BGT_COLOSSUS_SCALE,BGT_COLOSSUS_SCALE,
          BGT_COLOSSUS_SCALE,BGT_COLOSSUS_SCALE,0xFF,0xFF,0xFF,0xFF,BGT_COLOSSUS_EDGE_R,0xFF },
        { BGT_COLOSSUS_HORN,BGT_COLOSSUS_EDGE_L,BGT_COLOSSUS_SCALE,BGT_COLOSSUS_SCALE,
          BGT_COLOSSUS_SCALE,BGT_COLOSSUS_SCALE,BGT_COLOSSUS_SCALE,BGT_COLOSSUS_SCALE,
          BGT_COLOSSUS_SCALE,BGT_COLOSSUS_SCALE,BGT_COLOSSUS_SCALE,BGT_COLOSSUS_SCALE,
          BGT_COLOSSUS_SCALE,BGT_COLOSSUS_SCALE,BGT_COLOSSUS_EDGE_R,BGT_COLOSSUS_HORN },
        { BGT_COLOSSUS_EDGE_L,BGT_COLOSSUS_SCALE,BGT_COLOSSUS_VOID,BGT_COLOSSUS_VOID,
          BGT_COLOSSUS_EYE,BGT_COLOSSUS_VOID,BGT_COLOSSUS_VOID,BGT_COLOSSUS_RUNE,
          BGT_COLOSSUS_RUNE,BGT_COLOSSUS_VOID,BGT_COLOSSUS_VOID,BGT_COLOSSUS_EYE,
          BGT_COLOSSUS_VOID,BGT_COLOSSUS_VOID,BGT_COLOSSUS_SCALE,BGT_COLOSSUS_EDGE_R },
        { BGT_COLOSSUS_EDGE_L,BGT_COLOSSUS_VOID,BGT_COLOSSUS_VOID,BGT_COLOSSUS_SCALE,
          BGT_COLOSSUS_VOID,BGT_COLOSSUS_VOID,BGT_COLOSSUS_RUNE,BGT_COLOSSUS_RUNE,
          BGT_COLOSSUS_RUNE,BGT_COLOSSUS_RUNE,BGT_COLOSSUS_VOID,BGT_COLOSSUS_VOID,
          BGT_COLOSSUS_SCALE,BGT_COLOSSUS_VOID,BGT_COLOSSUS_VOID,BGT_COLOSSUS_EDGE_R },
        { BGT_COLOSSUS_EDGE_L,BGT_COLOSSUS_VOID,BGT_COLOSSUS_FANG,BGT_COLOSSUS_VOID,
          BGT_COLOSSUS_VOID,BGT_COLOSSUS_VOID,BGT_COLOSSUS_RUNE,BGT_COLOSSUS_RUNE,
          BGT_COLOSSUS_RUNE,BGT_COLOSSUS_RUNE,BGT_COLOSSUS_VOID,BGT_COLOSSUS_VOID,
          BGT_COLOSSUS_VOID,BGT_COLOSSUS_FANG,BGT_COLOSSUS_VOID,BGT_COLOSSUS_EDGE_R },
        { BGT_COLOSSUS_EDGE_L,BGT_COLOSSUS_SCALE,BGT_COLOSSUS_VOID,BGT_COLOSSUS_VOID,
          BGT_COLOSSUS_VOID,BGT_COLOSSUS_VOID,BGT_COLOSSUS_MAW,BGT_COLOSSUS_MAW,
          BGT_COLOSSUS_MAW,BGT_COLOSSUS_MAW,BGT_COLOSSUS_VOID,BGT_COLOSSUS_VOID,
          BGT_COLOSSUS_VOID,BGT_COLOSSUS_VOID,BGT_COLOSSUS_SCALE,BGT_COLOSSUS_EDGE_R },
        { BGT_COLOSSUS_EDGE_L,BGT_COLOSSUS_VOID,BGT_COLOSSUS_FANG,BGT_COLOSSUS_VOID,
          BGT_COLOSSUS_VOID,BGT_COLOSSUS_VOID,BGT_COLOSSUS_MAW,BGT_COLOSSUS_MAW,
          BGT_COLOSSUS_MAW,BGT_COLOSSUS_MAW,BGT_COLOSSUS_VOID,BGT_COLOSSUS_VOID,
          BGT_COLOSSUS_VOID,BGT_COLOSSUS_FANG,BGT_COLOSSUS_VOID,BGT_COLOSSUS_EDGE_R },
        { BGT_COLOSSUS_EDGE_L,BGT_COLOSSUS_SCALE,BGT_COLOSSUS_VOID,BGT_COLOSSUS_VOID,
          BGT_COLOSSUS_SCALE,BGT_COLOSSUS_VOID,BGT_COLOSSUS_VOID,BGT_COLOSSUS_RUNE,
          BGT_COLOSSUS_RUNE,BGT_COLOSSUS_VOID,BGT_COLOSSUS_VOID,BGT_COLOSSUS_SCALE,
          BGT_COLOSSUS_VOID,BGT_COLOSSUS_VOID,BGT_COLOSSUS_SCALE,BGT_COLOSSUS_EDGE_R },
        { 0xFF,BGT_COLOSSUS_EDGE_L,BGT_COLOSSUS_SCALE,BGT_COLOSSUS_SCALE,
          BGT_COLOSSUS_SCALE,BGT_COLOSSUS_SCALE,BGT_COLOSSUS_SCALE,BGT_COLOSSUS_SCALE,
          BGT_COLOSSUS_SCALE,BGT_COLOSSUS_SCALE,BGT_COLOSSUS_SCALE,BGT_COLOSSUS_SCALE,
          BGT_COLOSSUS_SCALE,BGT_COLOSSUS_SCALE,BGT_COLOSSUS_EDGE_R,0xFF },
        { 0xFF,0xFF,BGT_COLOSSUS_EDGE_L,BGT_COLOSSUS_EDGE_L,BGT_COLOSSUS_SCALE,
          BGT_COLOSSUS_SCALE,BGT_COLOSSUS_SCALE,BGT_COLOSSUS_SCALE,BGT_COLOSSUS_SCALE,
          BGT_COLOSSUS_SCALE,BGT_COLOSSUS_SCALE,BGT_COLOSSUS_SCALE,
          BGT_COLOSSUS_EDGE_R,BGT_COLOSSUS_EDGE_R,0xFF,0xFF },
    };
    u8 x, y;
    for (y = 0; y < 10; ++y)
        for (x = 0; x < 16; ++x)
            if (body[y][x] != 0xFF) room_tilemap[y + 2][x + 2] = body[y][x];
}

void tiles_prepare_colossal_edges(void) BANKED {
    u8 x, y;
    u8 edge = BGT_WALL;
    u8 edge_attr = BGPAL_WALL;
    // The playfield is 20x17 tiles. Camera sway can sample one pixel into the
    // next BG row/column, so initialize both rather than showing stale room-
    // transition VRAM at the edge of an otherwise colossal silhouette.
    for (y = 0; y < ROOM_H; ++y) {
        VBK_REG = 0; set_bkg_tiles(ROOM_W, y, 1, 1, &edge);
        VBK_REG = 1; set_bkg_tiles(ROOM_W, y, 1, 1, &edge_attr);
    }
    for (x = 0; x <= ROOM_W; ++x) {
        VBK_REG = 0; set_bkg_tiles(x, ROOM_H, 1, 1, &edge);
        VBK_REG = 1; set_bkg_tiles(x, ROOM_H, 1, 1, &edge_attr);
    }
    VBK_REG = 0;
}

void tiles_animate_colossus_bg(u8 closed) BANKED {
    set_bkg_data(BGT_COLOSSUS_EYE, 1,
        closed ? bgt_colossus_eye_closed : bgt_colossus_eye_open);
}

void tiles_animate_hydra_bg(u8 center_open) BANKED {
    // Side heads breathe while the centre clenches, then exchange roles.
    set_bkg_data(BGT_COLOSSUS_EYE, 1,
        center_open ? bgt_hydra_head_closed : bgt_hydra_head_open);
    set_bkg_data(BGT_COLOSSUS_MAW, 1,
        center_open ? bgt_hydra_head_open : bgt_hydra_head_closed);
}

void tiles_animate_cinder_bg(u8 active) BANKED {
    // Breath and lunge open the furnace face; recovery visibly clenches it.
    set_bkg_data(BGT_COLOSSUS_EYE, 1,
        active ? bgt_cinder_eye_open : bgt_cinder_eye_closed);
    set_bkg_data(BGT_COLOSSUS_MAW, 1,
        active ? bgt_cinder_maw_open : bgt_cinder_maw_closed);
}

void tiles_animate_serpent_bg(u8 alternate) BANKED {
    set_bkg_data(BGT_COLOSSUS_RUNE, 1,
        alternate ? bgt_serpent_rune_b : bgt_serpent_rune_a);
}

void tiles_animate_spider_bg(u8 closed) BANKED {
    set_bkg_data(BGT_COLOSSUS_EYE, 1,
        closed ? bgt_spider_eye_closed : bgt_spider_eye_open);
    set_bkg_data(BGT_COLOSSUS_RUNE, 1,
        closed ? bgt_spider_web_b : bgt_spider_web_a);
}

void tiles_animate_reaper_bg(u8 phased) BANKED {
    set_bkg_data(BGT_COLOSSUS_VOID, 1,
        phased ? bgt_reaper_void_b : bgt_reaper_void_a);
    set_bkg_data(BGT_COLOSSUS_EYE, 1,
        phased ? bgt_reaper_eye_closed : bgt_reaper_eye_open);
}

void tiles_animate_golem_bg(u8 dormant) BANKED {
    // The guardian periodically goes stone-still, then its eyes and paired
    // chest seals ignite together before the next dense ring.
    set_bkg_data(BGT_COLOSSUS_EYE, 1,
        dormant ? bgt_golem_eye_closed : bgt_golem_eye_open);
    set_bkg_data(BGT_COLOSSUS_RUNE, 1,
        dormant ? bgt_golem_rune_dim : bgt_golem_rune_bright);
}
