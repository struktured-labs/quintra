#pragma bank 255
// Hexa Dragmar. Five class limbs tick independently. The spotlight and the
// fairness shunt never pause another limb's state machine.

#include <gb/gb.h>
#include <gb/cgb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/boss_projectile.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/hexa_boss.h"
#include "game/player.h"
#include "game/procgen.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/hexa_bg.h"
#include "render/large_boss.h"
#include "render/palette.h"
#include "render/tiles.h"
#include "content.h"

u8 hexa_boss_active;
u8 hexa_core_entity;
u8 hexa_spotlight_limb;
u8 hexa_spotlight_timer;
u8 hexa_phase;
u8 hexa_limb_state[5];
u8 hexa_limb_timer[5];
u8 hexa_mark_x;
u8 hexa_mark_y;
u8 hexa_audio_ch1_claims;
u8 hexa_audio_ch2_claims;
u8 hexa_audio_ch3_claims;
u8 hexa_audio_ch4_claims;

static u8 last_spot;
static u8 applied_spot;
static u8 hit_part;
static u8 sauran_guard;
static u8 roar_timer;
static u8 converge;
static u8 half_tick;
static u16 fight_clock;
static u8 limb_aim[5];
static u8 limb_attack[5];
static u8 limb_cycle[5];
static u8 limb_stagger[5];
u8 hexa_limb_flash[5];
static u8 limb_burst[5];
i8 hexa_limb_ox[5];
i8 hexa_limb_oy[5];
/* GPT Image 2.6 Sunburst pass 2: authored 16x16 class heads,
   two poses each, packed as 5*8 8x8 tiles (idle then telegraph). */
static const u8 limb_art[640] = {
    0x10,0x10,0x28,0x38,0x54,0x6C,0x5B,0x67,0x59,0x65,0x59,0x64,0x28,0x37,0x10,0x1F,
    0x08,0x08,0x14,0x1C,0x2A,0x36,0xEA,0x9E,0x9A,0xA6,0x9A,0x26,0x14,0xEC,0x10,0xF0,
    0x11,0x1F,0x20,0x3F,0x40,0x7F,0x40,0x7C,0x40,0x7F,0x20,0x3F,0x10,0x1F,0x08,0x0F,
    0x88,0xF8,0x04,0xFC,0x02,0xFE,0x02,0x1E,0x02,0xFE,0x04,0xFC,0x10,0xF0,0x20,0xE0,
    0x10,0x10,0x28,0x38,0x54,0x6C,0x5B,0x67,0x59,0x65,0x59,0x64,0x28,0x37,0x10,0x1F,
    0x08,0x08,0x14,0x1C,0x2A,0x36,0xEA,0x9E,0x9A,0xA6,0x9A,0x26,0x14,0xEC,0x10,0xF0,
    0x10,0x1F,0x23,0x3F,0x43,0x7C,0x41,0x7D,0x41,0x7C,0x20,0x3E,0x10,0x1F,0x08,0x0F,
    0x10,0xF0,0xE4,0xFC,0xE2,0x1E,0xC2,0xDE,0x42,0x1E,0x04,0x3C,0x10,0xF0,0x20,0xE0,
    0x03,0x07,0x0B,0x0F,0x14,0x1F,0x28,0x3F,0x7F,0x7F,0x50,0x6F,0x51,0x6D,0x51,0x6C,
    0x80,0xC0,0xD0,0xF0,0x28,0xF8,0x14,0xFC,0xFC,0xFC,0x14,0xEC,0x94,0xAC,0x94,0x2C,
    0x28,0x37,0x10,0x1F,0x20,0x3F,0x40,0x7F,0x40,0x7E,0x20,0x3F,0x10,0x1F,0x08,0x0F,
    0x14,0xEC,0x08,0xF8,0x04,0xFC,0x04,0xFC,0x04,0x7C,0x08,0xF8,0x10,0xF0,0x20,0xE0,
    0x03,0x07,0x0B,0x0F,0x14,0x1F,0x28,0x3F,0x7F,0x7F,0x50,0x6F,0x51,0x6D,0x51,0x6C,
    0x80,0xC0,0xD0,0xF0,0x28,0xF8,0x14,0xFC,0xFC,0xFC,0x14,0xEC,0x94,0xAC,0x94,0x2C,
    0x28,0x37,0x11,0x1E,0x23,0x3F,0x41,0x7C,0x40,0x7C,0x20,0x3F,0x10,0x1F,0x08,0x0F,
    0x14,0xEC,0x88,0x78,0xC8,0xF8,0x84,0x3C,0x04,0x3C,0x08,0xF8,0x10,0xF0,0x20,0xE0,
    0x08,0x0F,0x11,0x1F,0x20,0x3D,0x40,0x7B,0x40,0x7F,0x28,0x34,0x29,0x35,0x14,0x1B,
    0x10,0xF0,0x08,0xF8,0x04,0xBC,0x02,0xDE,0x04,0xFC,0x14,0x2C,0x94,0xAC,0x28,0xD8,
    0x0A,0x0D,0x0B,0x0F,0x03,0x07,0x01,0x07,0x01,0x03,0x01,0x03,0x01,0x01,0x00,0x01,
    0x50,0xB0,0xD0,0xF0,0xC0,0xE0,0x80,0xE0,0x80,0xC0,0x80,0xC0,0x80,0x80,0x00,0x80,
    0x08,0x0F,0x11,0x1F,0x20,0x3D,0x40,0x7B,0x40,0x7F,0x28,0x34,0x29,0x35,0x14,0x1B,
    0x10,0xF0,0x08,0xF8,0x04,0xBC,0x02,0xDE,0x04,0xFC,0x14,0x2C,0x94,0xAC,0x28,0xD8,
    0x0B,0x0F,0x02,0x06,0x02,0x06,0x01,0x07,0x01,0x03,0x01,0x03,0x01,0x01,0x00,0x01,
    0xD0,0xF0,0x40,0x60,0xC0,0xE0,0x80,0xE0,0x80,0xC0,0x80,0xC0,0x80,0x80,0x00,0x80,
    0x00,0x03,0x00,0x0F,0x00,0x1F,0x00,0x3F,0x00,0x7F,0x1F,0x6F,0x38,0x50,0x38,0x51,
    0x00,0xC0,0x00,0xF0,0x00,0xF8,0x00,0xFC,0x00,0xFE,0xF0,0xEC,0x1C,0x2A,0x1C,0x2A,
    0x1F,0x6F,0x00,0x7F,0x00,0x79,0x40,0x7F,0x20,0x3E,0x10,0x1F,0x08,0x0F,0x00,0x07,
    0xF0,0xEC,0x00,0xFC,0x00,0x9E,0x04,0xFC,0x08,0x78,0x10,0xF0,0x20,0xE0,0x00,0xC0,
    0x00,0x03,0x00,0x0F,0x00,0x1F,0x00,0x3F,0x00,0x7F,0x1F,0x6F,0x38,0x50,0x38,0x51,
    0x00,0xC0,0x00,0xF0,0x00,0xF8,0x00,0xFC,0x00,0xFE,0xF0,0xEC,0x1C,0x2A,0x1C,0x2A,
    0x1C,0x6C,0x01,0x7D,0x01,0x7C,0x40,0x7C,0x20,0x3E,0x10,0x1F,0x08,0x0F,0x00,0x07,
    0x38,0x36,0x80,0xBC,0x80,0x3C,0x04,0x3C,0x08,0x78,0x10,0xF0,0x20,0xE0,0x00,0xC0,
    0x80,0x80,0x60,0x60,0x30,0x30,0x10,0x10,0x10,0x0F,0x20,0x1F,0x78,0x37,0x68,0x27,
    0x01,0x01,0x06,0x06,0x0C,0x0C,0x08,0x08,0x10,0xE0,0x08,0xF0,0x78,0xB0,0x58,0x90,
    0x78,0x37,0x18,0x6F,0x08,0x77,0x19,0x27,0x0F,0x13,0x0F,0x07,0x0C,0x04,0x04,0x00,
    0x78,0xB0,0x70,0xA8,0x20,0xD8,0x90,0xE0,0xC0,0xA0,0xC0,0x80,0xC0,0x80,0x80,0x00,
    0x88,0x88,0x60,0x60,0x30,0x30,0x10,0x10,0x10,0x0F,0x20,0x1F,0x68,0x27,0x78,0x37,
    0x00,0x04,0x06,0x06,0x0C,0x0C,0x08,0x08,0x10,0xE0,0x08,0xF0,0x58,0x90,0x78,0xB0,
    0x68,0x27,0x18,0x6F,0x08,0x77,0x1C,0x2C,0x0B,0x18,0x07,0x0F,0x0C,0x04,0x04,0x00,
    0x58,0x90,0x70,0xA8,0x20,0xD8,0x38,0x30,0x20,0x30,0x80,0xC0,0xC0,0x80,0x80,0x00,
};

static const u8 limb_x[5] = { 32, 112, 24, 120, 72 };
static const u8 limb_y[5] = { 72, 72, 32, 32, 16 };
static const u8 idle_reload[5] = { 37, 43, 35, 41, 29 };
static const u8 tele_len[5] = { 20, 24, 18, 22, 16 };
static const u8 active_a[5] = { 18, 20, 16, 14, 10 };
static const u8 active_b[5] = { 12, 28, 16, 36, 80 };
static const u8 rec_len[5] = { 34, 32, 30, 36, 28 };
static const u8 spawn_idle[5] = { 19, 43, 11, 53, 31 };

static const u16 tele_obj[4] = {
    BGR555(0, 0, 0), BGR555(31, 24, 12), BGR555(31, 31, 20), BGR555(31, 31, 31)
};
static const u16 spot_obj[20] = {
    BGR555(0, 0, 0), BGR555(14, 6, 4), BGR555(28, 12, 6), BGR555(31, 31, 28),
    BGR555(0, 0, 0), BGR555(4, 12, 4), BGR555(8, 26, 8), BGR555(31, 31, 28),
    BGR555(0, 0, 0), BGR555(6, 6, 16), BGR555(12, 14, 30), BGR555(31, 31, 28),
    BGR555(0, 0, 0), BGR555(4, 10, 14), BGR555(8, 22, 28), BGR555(31, 31, 28),
    BGR555(0, 0, 0), BGR555(16, 12, 2), BGR555(30, 24, 4), BGR555(31, 31, 28)
};

static u8 aim_toward(i16 x, i16 y, i16 tx, i16 ty) {
    i8 sx = (tx > x) ? 1 : (tx < x) ? -1 : 0;
    i8 sy = (ty > y) ? 1 : (ty < y) ? -1 : 0;
    u8 d;
    for (d = 0; d < 8; ++d)
        if (dir8_dx[d] == sx && dir8_dy[d] == sy) return d;
    return 4;
}

static u8 aim8(i16 x, i16 y) {
    return aim_toward(x, y, player.x, player.y);
}

static void note_ch1(void) {
    if (hexa_audio_ch1_claims < 255) hexa_audio_ch1_claims++;
}

static void note_ch4(void) {
    if (hexa_audio_ch4_claims < 255) hexa_audio_ch4_claims++;
}

static void motif(u8 limb) {
    static const u16 pitch[5] = { 1480, 1120, 1760, 1600, 1880 };
    static const u8 duty[5] = { 0x80, 0xC0, 0x40, 0x80, 0x40 };
    u16 freq = pitch[limb];
    sfx_claim_channels(14, 0);
    NR10_REG = 0x15;
    NR11_REG = duty[limb];
    NR12_REG = 0xA2;
    NR13_REG = (u8)freq;
    NR14_REG = (u8)(0x80 | (freq >> 8));
    note_ch1();
}

static void attack_noise(u8 roar) {
    if (roar) {
        sfx_play(SFX_ROAR);
        note_ch1();
    } else {
        sfx_play(SFX_HIT);
    }
    note_ch4();
}

static u8 spawn_at(i16 x, i16 y, u8 dir, u8 pattern, u8 speed,
                   u8 dmg, u8 ttl, u8 limb, u8 hitbox) {
    u8 slot, i, tag, angle;
    dir &= 7;
    angle = (u8)(dir << 2);
    slot = boss_projectile_spawn(x, y, angle, pattern, 0, dmg);
    if (slot == 0xFF) {
        for (i = 0; i < MAX_ENTITIES; ++i) {
            if ((entities[i].flags & EF_ACTIVE)
                && entities[i].type == ENT_PROJECTILE
                && !(entities[i].flags & EF_PLAYER_PROJ)
                && entities[i].state_timer < 20) {
                entity_kill(i);
                break;
            }
        }
        slot = boss_projectile_spawn(x, y, angle, pattern, 0, dmg);
    }
    if (slot == 0xFF) return 0xFF;
    entities[slot].state = (speed >= 4) ? 3 : (speed <= 2) ? 1 : 0;
    if (ttl) entities[slot].state_timer = ttl;
    if (hitbox) entities[slot].hitbox = hitbox;
    tag = (u8)(0x80 | (limb & 7));
    if (dir == 0 || dir == 4) {
        if (!hitbox) entities[slot].hitbox = 0x6E;
        tag |= 0x10;
    } else if (dir == 6) {
        tag |= 0x08;
    }
    entities[slot].ai_data[5] = tag;
    return slot;
}

static void clear_limb_shots(u8 limb) {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if ((entities[i].flags & EF_ACTIVE)
            && entities[i].type == ENT_PROJECTILE
            && (entities[i].ai_data[5] & 0x87) == (u8)(0x80 | limb))
            entity_kill(i);
    }
}

static void clear_player_near(i16 x, i16 y) {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        i16 dx, dy;
        entity_t *s = &entities[i];
        if (!(s->flags & EF_ACTIVE) || s->type != ENT_PROJECTILE) continue;
        if (!(s->flags & EF_PLAYER_PROJ) || s->hp > 1) continue;
        dx = s->x - x;
        dy = s->y - y;
        if (dx < 0) dx = (i16)-dx;
        if (dy < 0) dy = (i16)-dy;
        if (dx <= 32 && dy <= 32) entity_kill(i);
    }
}

static void load_spot(u8 limb) {
    palette_obj_load(6, &spot_obj[limb * 4]);
}

static void load_body_pals(void) {
    palette_obj_load(7, tele_obj);
}

void hexa_refresh_attrs(void) BANKED {
    load_body_pals();
    hexa_bg_stamp(hexa_spotlight_limb, hexa_phase);
    if (hexa_spotlight_limb < 5) load_spot(hexa_spotlight_limb);
    applied_spot = hexa_spotlight_limb;
}

static u8 limb_tiles[640];

static void gen_limb_tiles(void) {
    u16 i;
    /* Keep the original WRAM buffer so suspend/resume RAM layout is unchanged. */
    for (i = 0; i < 640; ++i) limb_tiles[i] = limb_art[i];
    VBK_REG = 1;
    set_sprite_data(HEXA_LIMB_TILE, 40, limb_tiles);
    VBK_REG = 0;
}

static void paint_carapace(void) {
    hexa_bg_prepare();
}

void hexa_boss_clear(void) BANKED {
    hexa_boss_active = 0;
}

void hexa_sanctum_enter(void) BANKED {
    u8 i, idx;
    room_world_width = 160;
    room_world_height = 128;
    room_camera_x = 0;
    room_camera_y = 0;
    room_bg_origin_x = 0;
    room_bg_origin_y = 0;
    procgen_current_room_is_boss = 1;
    procgen_current_room_is_large = 0;
    serpent_tail_active = 0;
    cinder_pack_active = 0;
    large_boss_index = 255;
    room_combat_sealed = 0;
    entity_init_room();
    paint_carapace();
    boss_projectile_load_art();
    gen_limb_tiles();
    player.x = 72;
    player.y = 96;
    player.iframes = 45;
    idx = enemy_spawn(ENEMY_STONE_SENTINEL, 9, 5);
    if (idx == 0xFF) idx = entity_spawn(ENT_ENEMY);
    hexa_core_entity = idx;
    if (idx != 0xFF) {
        entity_t *e = &entities[idx];
        e->x = 72;
        e->y = 40;
        e->vx = 0;
        e->vy = 0;
        e->hp = 255;
        e->damage = 1;
        e->hitbox = 0xEE;
        e->palette = 5;
        e->sprite_tile = HEXA_LIMB_TILE;
        e->ai_data[0] = ENEMY_STONE_SENTINEL;
        e->ai_data[1] = 0;
        e->ai_data[2] = HEXA_STAGE;
        e->ai_data[3] = 1;
        e->ai_data[4] = 0;
        e->ai_data[5] = 0;
        e->ai_data[6] = 255;
        e->ai_data[7] = 0;
        e->flags |= EF_ON_SCREEN | EF_ACTIVE | EF_ALIVE;
        e->type = ENT_ENEMY;
    }
    for (i = 0; i < 5; ++i) {
        hexa_limb_state[i] = HEXA_LIMB_IDLE;
        hexa_limb_timer[i] = spawn_idle[i];
        limb_aim[i] = 4;
        limb_attack[i] = 0;
        limb_cycle[i] = 0;
        limb_stagger[i] = 0;
        hexa_limb_flash[i] = 0;
        limb_burst[i] = 0;
        hexa_limb_ox[i] = 0;
        hexa_limb_oy[i] = 0;
    }
    hexa_spotlight_limb = 0xFF;
    hexa_spotlight_timer = 90;
    last_spot = 0xFF;
    applied_spot = 0xFE;
    hit_part = 0xFF;
    sauran_guard = 0;
    roar_timer = 0;
    converge = 0;
    half_tick = 0;
    fight_clock = 0;
    hexa_phase = 0;
    hexa_mark_x = 72;
    hexa_mark_y = 64;
    hexa_audio_ch1_claims = 0;
    hexa_audio_ch2_claims = 0;
    hexa_audio_ch3_claims = 0;
    hexa_audio_ch4_claims = 0;
    hexa_boss_active = 1;
    load_body_pals();
    attack_noise(1);
}

static void place_head(u8 i) {
    i8 ox = 0, oy = 0;
    u8 st = hexa_limb_state[i];
    u8 d = limb_aim[i] & 7;
    if (st == HEXA_LIMB_IDLE) {
        ox = ((entity_anim_counter + (u8)(i * 13)) & 16) ? 1 : -1;
    } else if (st == HEXA_LIMB_TELEGRAPH) {
        ox = (i8)(-dir8_dx[d] * 4);
        oy = (i8)(-dir8_dy[d] * 4);
    } else if (st == HEXA_LIMB_ACTIVE) {
        ox = (i8)(dir8_dx[d] * 6);
        oy = (i8)(dir8_dy[d] * 6);
    }
    if (ox > 12) ox = 12;
    if (ox < -12) ox = -12;
    if (oy > 12) oy = 12;
    if (oy < -12) oy = -12;
    hexa_limb_ox[i] = ox;
    hexa_limb_oy[i] = oy;
}

static void fire_open(u8 i) {
    u8 d = limb_aim[i] & 7;
    i16 x = (i16)limb_x[i] + 8;
    i16 y = (i16)limb_y[i] + 8;
    i8 px = (i8)(-dir8_dy[d] * 6);
    i8 py = (i8)(dir8_dx[d] * 6);
    limb_burst[i] = 0;
    if (!limb_attack[i]) {
        if (i == 0) {
            spawn_at(x, y, d, BOSS_SHOT_BOLT, 3, 1, 24, i, 0);
            spawn_at((i16)(x + px), (i16)(y + py), d, BOSS_SHOT_BOLT, 3, 1, 24, i, 0);
            spawn_at((i16)(x - px), (i16)(y - py), d, BOSS_SHOT_BOLT, 3, 1, 24, i, 0);
        } else if (i == 1) {
            spawn_at(x, y, d, BOSS_SHOT_BOLT, 4, 2, 28, i, 0);
        } else if (i == 2) {
            spawn_at(x, y, (u8)(d + 7), BOSS_SHOT_RETURN, 3, 1, 70, i, 0);
            spawn_at(x, y, (u8)(d + 1), BOSS_SHOT_RETURN, 3, 1, 70, i, 0);
        } else if (i == 3) {
            spawn_at(x, y, d, BOSS_SHOT_WAVE, 2, 1, 80, i, 0xEE);
            limb_burst[i] = 1;
        } else {
            spawn_at(x, y, d, BOSS_SHOT_BOLT, 4, 1, 24, i, 0);
            limb_burst[i] = 1;
        }
    } else if (i == 0) {
        u8 k;
        for (k = 0; k < 8; ++k)
            spawn_at(x, y, k, BOSS_SHOT_ARC, 3, 1, 28, i, 0x66);
        clear_player_near(x, y);
        attack_noise(1);
        return;
    } else if (i == 1) {
        sauran_guard = 1;
    } else if (i == 2) {
        spawn_at(x, y, aim_toward(x, y, hexa_mark_x, hexa_mark_y),
                 BOSS_SHOT_BOLT, 4, 1, 28, i, 0);
        spawn_at(16, 16, aim_toward(16, 16, hexa_mark_x, hexa_mark_y),
                 BOSS_SHOT_BOLT, 4, 1, 28, i, 0);
        spawn_at(144, 16, aim_toward(144, 16, hexa_mark_x, hexa_mark_y),
                 BOSS_SHOT_BOLT, 4, 1, 28, i, 0);
    } else if (i == 3) {
        spawn_at(x, y, d, BOSS_SHOT_WAVE, 2, 1, 80, i, 0xEE);
        spawn_at(x, y, (u8)(d + 2), BOSS_SHOT_WAVE, 2, 1, 80, i, 0xEE);
        spawn_at(x, y, (u8)(d + 6), BOSS_SHOT_WAVE, 2, 1, 80, i, 0xEE);
        spawn_at(x, y, (u8)(d + 1), BOSS_SHOT_WAVE, 2, 1, 80, i, 0xEE);
        limb_burst[i] = 1;
    } else {
        spawn_at(x, y, d, BOSS_SHOT_ARC, 4, 1, 24, i, 0);
        limb_burst[i] = 1;
    }
    attack_noise(0);
}

static void fire_sustain(u8 i) {
    u8 d = limb_aim[i] & 7;
    i16 x = (i16)limb_x[i] + 8;
    i16 y = (i16)limb_y[i] + 8;
    if (i == 1 && !limb_attack[i] && limb_burst[i] == 0
        && hexa_limb_timer[i] == 8) {
        spawn_at(x, y, (u8)(d + 7), BOSS_SHOT_BOLT, 3, 1, 16, i, 0);
        spawn_at(x, y, d, BOSS_SHOT_BOLT, 3, 1, 16, i, 0);
        spawn_at(x, y, (u8)(d + 1), BOSS_SHOT_BOLT, 3, 1, 16, i, 0);
        limb_burst[i] = 1;
    } else if (i == 3 && !limb_attack[i] && limb_burst[i] == 1
        && hexa_limb_timer[i] == 2) {
        spawn_at(x, y, (u8)(d + 1), BOSS_SHOT_WAVE, 2, 1, 80, i, 0xEE);
        limb_burst[i] = 2;
    } else if (i == 4 && !limb_attack[i] && limb_burst[i] == 1
        && hexa_limb_timer[i] == 1) {
        spawn_at(x, y, d, BOSS_SHOT_BOLT, 4, 1, 24, i, 0);
        limb_burst[i] = 2;
    } else if (i == 4 && limb_attack[i] && limb_burst[i] < 6) {
        u8 elapsed = (u8)(80 - hexa_limb_timer[i]);
        if (elapsed && (elapsed % 16) == 0) {
            spawn_at(x, y, (u8)(d + limb_burst[i]), BOSS_SHOT_ARC, 4, 1, 24, i, 0);
            limb_burst[i]++;
        }
    }
}

static void lock_mark(void) {
    i16 x = (i16)player.x + 8;
    i16 y = (i16)player.y + 8;
    u8 i;
    if (x < 28) x = 28;
    if (x > 132) x = 132;
    if (y < 20) y = 20;
    if (y > 96) y = 96;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        i16 dx, dy;
        entity_t *s = &entities[i];
        if (!(s->flags & EF_ACTIVE)) continue;
        if ((s->ai_data[5] & 0x87) != (0x80 | 3)) continue;
        dx = x - s->x;
        dy = y - s->y;
        if (dx < 0) dx = (i16)-dx;
        if (dy < 0) dy = (i16)-dy;
        if (dx < 24 && dy < 24) y = 96;
    }
    hexa_mark_x = (u8)x;
    hexa_mark_y = (u8)y;
}

static void shunt(void) {
    u8 i, n = 0, min_t = 255, extra = 0;
    u8 ids[5];
    for (i = 0; i < 5; ++i) {
        if (hexa_limb_state[i] != HEXA_LIMB_TELEGRAPH) continue;
        if (hexa_limb_timer[i] < min_t) min_t = hexa_limb_timer[i];
    }
    for (i = 0; i < 5; ++i) {
        if (hexa_limb_state[i] != HEXA_LIMB_TELEGRAPH) continue;
        if ((u8)(hexa_limb_timer[i] - min_t) <= 6)
            ids[n++] = i;
    }
    if (n < 3) return;
    for (i = 2; i < n; ++i) {
        extra = (u8)(extra + 10);
        hexa_limb_timer[ids[i]] = (u8)(hexa_limb_timer[ids[i]] + extra);
    }
}

static void spotlight_tick(void) {
    u8 gap = (hexa_phase >= 1) ? 45 : 90;
    if (hexa_spotlight_timer) hexa_spotlight_timer--;
    if (!hexa_spotlight_timer) {
        if (hexa_spotlight_limb == 0xFF) {
            u8 n = last_spot;
            u8 step = (u8)(1u + (run_state.room_counter & 1));
            u8 k;
            if (n > 4) n = 4;
            for (k = 0; k < 5; ++k) {
                n = (u8)((n + step) % 5);
                if (hexa_limb_state[n] != HEXA_LIMB_BROKEN) break;
            }
            hexa_spotlight_limb = n;
            last_spot = n;
            hexa_spotlight_timer = 150;
            motif(n);
        } else {
            hexa_spotlight_limb = 0xFF;
            hexa_spotlight_timer = gap;
        }
    }
    if (applied_spot != hexa_spotlight_limb) {
        /* Recolor only the sockets that changed. Rewriting all five during
           the active frame blew past vblank and tore the limb timers. */
        hexa_bg_retint(applied_spot, hexa_spotlight_limb, hexa_phase);
        if (hexa_spotlight_limb < 5) load_spot(hexa_spotlight_limb);
        applied_spot = hexa_spotlight_limb;
    }
}

static void limb_tick(u8 i) {
    if (hexa_limb_state[i] == HEXA_LIMB_BROKEN) {
        hexa_limb_ox[i] = 0;
        hexa_limb_oy[i] = 6;
        if (half_tick) return;
        if (hexa_limb_timer[i]) hexa_limb_timer[i]--;
        if (!hexa_limb_timer[i]) {
            hexa_limb_state[i] = HEXA_LIMB_IDLE;
            hexa_limb_timer[i] = 24;
            limb_stagger[i] = 0;
        }
        return;
    }
    place_head(i);
    if (hexa_limb_flash[i]) hexa_limb_flash[i]--;
    if (hexa_limb_state[i] == HEXA_LIMB_TELEGRAPH
        && limb_attack[i] && i == 2 && (hexa_limb_timer[i] & 7) == 0)
        fx_spawn(SPR_FX_MUZZLE, 7, player.x, player.y, 8);
    if (hexa_limb_timer[i]) {
        hexa_limb_timer[i]--;
        if (hexa_limb_state[i] == HEXA_LIMB_TELEGRAPH && hexa_limb_timer[i] == 8) {
            hexa_limb_flash[i] = 8;
            sfx_play(SFX_TICK);
            note_ch4();
        }
        if (hexa_limb_state[i] == HEXA_LIMB_ACTIVE) fire_sustain(i);
        return;
    }
    if (hexa_limb_state[i] == HEXA_LIMB_IDLE) {
        limb_cycle[i]++;
        limb_aim[i] = aim8((i16)limb_x[i] + 8, (i16)limb_y[i] + 8);
        limb_attack[i] = ((limb_cycle[i] % 3) == 0 || hexa_spotlight_limb == i) ? 1 : 0;
        hexa_limb_state[i] = HEXA_LIMB_TELEGRAPH;
        hexa_limb_timer[i] = tele_len[i];
        limb_burst[i] = 0;
        return;
    }
    if (hexa_limb_state[i] == HEXA_LIMB_TELEGRAPH) {
        if (i == 2 && limb_attack[i]) lock_mark();
        hexa_limb_state[i] = HEXA_LIMB_ACTIVE;
        hexa_limb_timer[i] = limb_attack[i] ? active_b[i] : active_a[i];
        fire_open(i);
        return;
    }
    if (hexa_limb_state[i] == HEXA_LIMB_ACTIVE) {
        if (i == 4 && limb_attack[i] && limb_burst[i] < 6) {
            spawn_at((i16)limb_x[i] + 8, (i16)limb_y[i] + 8,
                     (u8)(limb_aim[i] + limb_burst[i]), BOSS_SHOT_ARC, 4, 1, 24, i, 0);
            limb_burst[i]++;
        }
        if (i == 1) sauran_guard = 0;
        hexa_limb_state[i] = HEXA_LIMB_RECOVERY;
        hexa_limb_timer[i] = rec_len[i];
        return;
    }
    hexa_limb_state[i] = HEXA_LIMB_IDLE;
    hexa_limb_timer[i] = idle_reload[i];
    if (hexa_phase >= 1 && hexa_limb_timer[i] > 8)
        hexa_limb_timer[i] = (u8)(hexa_limb_timer[i] - 6);
}

static void phase_tick(entity_t *e) {
    u8 next = 0, i;
    if (e->ai_data[6] == 0) e->ai_data[6] = 255;
    if (e->hp <= (u8)(e->ai_data[6] >> 1)) next = 1;
    if (e->hp <= (u8)(e->ai_data[6] >> 2)) next = 2;
    if (next > hexa_phase) {
        hexa_phase = next;
        roar_timer = 40;
        for (i = 0; i < MAX_ENTITIES; ++i) {
            if (entities[i].type == ENT_PROJECTILE
                && (entities[i].flags & EF_ACTIVE)
                && !(entities[i].flags & EF_PLAYER_PROJ))
                entity_kill(i);
        }
        attack_noise(1);
        room_shake(1, 16);
        hexa_bg_set_phase(hexa_phase, hexa_spotlight_limb);
    }
    if (roar_timer) roar_timer--;
}

static void converge_tick(void) {
    static const u8 ang[6] = { 0, 5, 11, 16, 22, 27 };
    u8 i;
    if (hexa_phase < 2) {
        converge = 0;
        return;
    }
    if (((u8)fight_clock) == 0 && converge == 0) converge = 48;
    if (!converge) return;
    converge--;
    if ((converge & 7) == 0) {
        fx_spawn(SPR_FX_IMPACT, 1, 8, 40, 8);
        fx_spawn(SPR_FX_IMPACT, 1, 136, 40, 8);
        fx_spawn(SPR_FX_IMPACT, 1, 72, 8, 8);
        fx_spawn(SPR_FX_IMPACT, 1, 72, 100, 8);
    }
    if ((converge & 3) == 0) hexa_bg_core_blink((converge & 4) ? 1 : 0);
    if (!converge) {
        hexa_bg_set_phase(hexa_phase, hexa_spotlight_limb);
        for (i = 0; i < 6; ++i) {
            u8 slot = boss_projectile_spawn(80, 48, ang[i], BOSS_SHOT_BOLT, 0, 1);
            if (slot == 0xFF) continue;
            entities[slot].state = 3;
            entities[slot].state_timer = 22;
            entities[slot].ai_data[5] = 0x80 | 5;
        }
        attack_noise(1);
    }
}

void hexa_boss_tick(entity_t *e) BANKED {
    u8 i;
    if (!hexa_boss_active || !e) return;
    e->x = 72;
    e->y = 40;
    fight_clock++;
    half_tick ^= 1;
    phase_tick(e);
    spotlight_tick();
    shunt();
    for (i = 0; i < 5; ++i) limb_tick(i);
    converge_tick();
}

static u8 box_hit(const entity_t *shot, i16 x, i16 y, u8 w, u8 h) {
    i16 sr = (i16)(shot->x + (shot->hitbox >> 4));
    i16 sb = (i16)(shot->y + (shot->hitbox & 15));
    if (sr <= x || shot->x >= (i16)(x + w)) return 0;
    if (sb <= y || shot->y >= (i16)(y + h)) return 0;
    return 1;
}

static u8 hero_hits(i16 x, i16 y, u8 w, u8 h) {
    i16 px = (i16)player.x + 5;
    i16 py = (i16)player.y + 9;
    if ((i16)(px + 6) <= x || (i16)(x + w) <= px) return 0;
    if ((i16)(py + 6) <= y || (i16)(y + h) <= py) return 0;
    return 1;
}

u8 hexa_shot_overlap(const entity_t *shot) BANKED {
    u8 i;
    hit_part = 0xFF;
    if (!hexa_boss_active) return 0;
    if (hexa_spotlight_limb < 5 && hexa_limb_state[hexa_spotlight_limb] != HEXA_LIMB_BROKEN) {
        i = hexa_spotlight_limb;
        if (box_hit(shot, (i16)limb_x[i] + hexa_limb_ox[i], (i16)limb_y[i] + hexa_limb_oy[i], 16, 16)) {
            hit_part = i;
            return 1;
        }
    }
    for (i = 0; i < 5; ++i) {
        if (i == hexa_spotlight_limb) continue;
        if (hexa_limb_state[i] == HEXA_LIMB_BROKEN) continue;
        if (box_hit(shot, (i16)limb_x[i] + hexa_limb_ox[i], (i16)limb_y[i] + hexa_limb_oy[i], 16, 16)) {
            hit_part = i;
            return 1;
        }
    }
    if (hexa_phase >= 1 && box_hit(shot, 72, 40, 16, 16)) {
        hit_part = 5;
        return 1;
    }
    return 0;
}

u8 hexa_touches_player(void) BANKED {
    u8 i;
    if (!hexa_boss_active) return 0;
    for (i = 0; i < 5; ++i) {
        if (hexa_limb_state[i] == HEXA_LIMB_BROKEN) continue;
        if (hero_hits((i16)limb_x[i] + hexa_limb_ox[i], (i16)limb_y[i] + hexa_limb_oy[i], 16, 16))
            return 1;
    }
    return hero_hits(72, 40, 16, 16);
}

u8 hexa_filter_damage(u8 dmg) BANKED {
    u8 part = hit_part;
    u8 cap = 3;
    entity_t *boss;
    if (!hexa_boss_active || hexa_core_entity >= MAX_ENTITIES) return dmg;
    boss = &entities[hexa_core_entity];
    if (part == 1 && sauran_guard) {
        sfx_play(SFX_HIT);
        note_ch4();
        return 0;
    }
    if (part == 3 && limb_burst[3] == 1 && limb_attack[3]
        && hexa_limb_state[3] == HEXA_LIMB_ACTIVE) {
        limb_burst[3] = 2;
        sfx_play(SFX_HIT);
        note_ch4();
        return 0;
    }
    if (part < 5 && hexa_spotlight_limb == part) cap = 5;
    if (dmg > cap) dmg = cap;
    if (part == 5 && sauran_guard) {
        dmg >>= 1;
        if (!dmg) dmg = 1;
    }
    if (part < 5 && hexa_limb_state[part] != HEXA_LIMB_BROKEN) {
        u8 sum = (u8)(limb_stagger[part] + dmg);
        if (sum < limb_stagger[part]) sum = 255;
        limb_stagger[part] = sum;
        hexa_limb_flash[part] = 6;
        if (limb_stagger[part] >= 60) {
            limb_stagger[part] = 0;
            hexa_limb_state[part] = HEXA_LIMB_BROKEN;
            hexa_limb_timer[part] = 180;
            clear_limb_shots(part);
            if (boss->hp > 16) boss->hp = (u8)(boss->hp - 15);
            else if (boss->hp > 1) boss->hp = 1;
            attack_noise(1);
            room_shake(1, 12);
        }
        if ((part == 0 || part == 2) && sauran_guard) {
            sauran_guard = 0;
            if (hexa_limb_state[1] == HEXA_LIMB_ACTIVE && limb_attack[1]) {
                hexa_limb_state[1] = HEXA_LIMB_RECOVERY;
                hexa_limb_timer[1] = rec_len[1];
            }
        }
    }
    return dmg ? dmg : 1;
}
