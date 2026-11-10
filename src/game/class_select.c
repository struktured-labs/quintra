#pragma bank 3
// CLASS_SELECT — pick a class for this run.
// Five-vessel class selection with live generated loadout previews.

#include <gb/gb.h>
#include <gb/cgb.h>
#include <gbdk/console.h>
#include <gbdk/font.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/class_select.h"
#include "game/player.h"
#include "render/class_palettes.h"
#include "render/palette.h"
#include "render/text.h"
#include "render/tiles.h"
#include "content.h"

BANKREF(class_select_enter)

u8 class_select_cursor;
u8 class_select_easy_mode;
u8 class_select_attr_phase;
u8 class_select_pal_steps;
u8 class_select_vbl_work;
u8 class_select_name_len;

static const u16 cs_palette[4] = {
    BGR555( 0,  2,  6),    // 0: deep blue
    BGR555( 6,  8, 18),    // 1: blue
    BGR555(20, 16, 28),    // 2: lavender
    BGR555(30, 30, 31),    // 3: white
};

static const u16 gold_palette[4] = {
    BGR555( 0,  2,  6),
    BGR555(12,  8,  2),
    BGR555(22, 16,  4),
    BGR555(31, 25,  6),
};

// Dim prompt/hint text: cs_palette color 2 promoted to font foreground.
static const u16 lavender_palette[4] = {
    BGR555( 0,  2,  6),
    BGR555( 4,  4, 12),
    BGR555(12, 10, 18),
    BGR555(20, 16, 28),
};

// Gold star cursor (reuses the bullet sprite tile)
static const u16 cursor_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555(31, 24,  0),
    BGR555(28, 16,  0),
    BGR555(31, 31,  4),
};

// Selection copy is deliberately player language, not content-table jargon.
// Each complete prefixed line fits the physical 20-column LCD.
static const char *const role_tips[N_CLASSES] = {
    "BLADE FIGHTER", "ARMORED TANK", "RANGED HUNTER",
    "MAGIC CASTER", "FAST STRIKER",
};

static const char *const primary_tips[N_CLASSES] = {
    "STAB SLASH DASH", "HEAVY TAIL STRIKE", "RETURNING FEATHER",
    "PIERCING BUBBLE", "FAST STINGER",
};

static const char *const signature_tips[N_CLASSES] = {
    "8 SHOTS BRIEF WARD", "BLOCKS ALL HITS", "MARK RAVEN DIVES",
    "3 BUBBLES AND WARD", "ROTATING STINGERS",
};

static const char *const trait_tips[N_CLASSES] = {
    "FAST MOVEMENT", "HEALTH REGEN", "SHOW ENEMY HP",
    "FAST MP REGEN", "ELEMENT POWER",
};

#define CS_PAL_BODY      0
#define CS_PAL_GOLD      1
#define CS_PAL_ACCENT    2
#define CS_PAL_LAVENDER  3

static void cache_copy(u8 slot, const u16 *colors) {
    u8 i;
    for (i = 0; i < 4; ++i) bg_pal_cache[slot][i] = colors[i];
}

static void cache_obj_copy(u8 slot, const u16 *colors) {
    u8 i;
    for (i = 0; i < 4; ++i) obj_pal_cache[slot][i] = colors[i];
}

// Fill the VBlank caches and arm a rotating multi-frame commit. Accent
// colors 1..3 come from the already-banked class OBJ table via WRAM.
static void cache_and_arm_palettes(void) {
    u8 slot;
    class_palette_cache_obj(1, class_select_cursor);
    cache_copy(CS_PAL_BODY, cs_palette);
    cache_copy(CS_PAL_GOLD, gold_palette);
    bg_pal_cache[CS_PAL_ACCENT][0] = cs_palette[0];
    bg_pal_cache[CS_PAL_ACCENT][1] = obj_pal_cache[1][1];
    bg_pal_cache[CS_PAL_ACCENT][2] = obj_pal_cache[1][2];
    bg_pal_cache[CS_PAL_ACCENT][3] = obj_pal_cache[1][3];
    cache_copy(CS_PAL_LAVENDER, lavender_palette);
    for (slot = 4; slot < 8; ++slot) cache_copy(slot, cs_palette);

    cache_obj_copy(2, cursor_palette);
    // Unused OBJ slots stay black so a leaked title spirit cannot show
    // leftover champion colors.
    obj_pal_cache[0][0] = 0; obj_pal_cache[0][1] = 0;
    obj_pal_cache[0][2] = 0; obj_pal_cache[0][3] = 0;
    for (slot = 3; slot < 8; ++slot) {
        obj_pal_cache[slot][0] = 0;
        obj_pal_cache[slot][1] = 0;
        obj_pal_cache[slot][2] = 0;
        obj_pal_cache[slot][3] = 0;
    }

    // Four half-bursts (BG lo/hi, OBJ lo/hi) per rotating pass.
    class_select_pal_steps = (u8)(PALETTE_OBJ_COMMIT_PASSES * 4);
    class_select_vbl_work = 1;
}

// Live 16x16 preview of the highlighted class, in its own colors.
static void update_preview(void) {
    u8 base = (u8)(SPR_CLASS_BASE + (u8)(class_select_cursor * SPR_CLASS_STRIDE));
    u8 sx = 128, sy = 72;
    set_sprite_tile(0, base);
    set_sprite_tile(1, (u8)(base + 1));
    set_sprite_tile(2, (u8)(base + 2));
    set_sprite_tile(3, (u8)(base + 3));
    set_sprite_prop(0, 0x01); set_sprite_prop(1, 0x01);
    set_sprite_prop(2, 0x01); set_sprite_prop(3, 0x01);
    move_sprite(0, sx,         sy);
    move_sprite(1, (u8)(sx+8), sy);
    move_sprite(2, sx,         (u8)(sy+8));
    move_sprite(3, (u8)(sx+8), (u8)(sy+8));
    // Cursor star beside the highlighted class row
    set_sprite_tile(4, SPR_BULLET);
    set_sprite_prop(4, 0x02);
    move_sprite(4, 16, (u8)((3 + class_select_cursor) * 8 + 16));
}

static void write_stats(const class_def_t *c) {
    gotoxy(0, 14);
    text_write("HP");
    text_u16((u16)c->base_stats.hp_max);
    // Picsean's MP 10 is one column over a spaced " MP"; color, not a
    // missing tile, separates HP digits from the MP label.
    if (c->base_stats.mp_max >= 10) text_write("MP");
    else text_write(" MP");
    text_u16((u16)c->base_stats.mp_max);
    text_write(" AT");
    text_u16((u16)c->base_stats.atk);
    text_write(" DF");
    text_u16((u16)c->base_stats.def);
    text_write(" SP");
    text_u16((u16)c->base_stats.spd);
}

static void render(void) {
    const class_def_t *c = &classes[class_select_cursor];
    u8 i;

    cls();
    gotoxy(2, 1);  text_write("CHOOSE YOUR HERO");

    for (i = 0; i < N_CLASSES; ++i) {
        gotoxy(2, (u8)(3 + i));
        if (i == class_select_cursor) text_write("> ");
        else                          text_write("  ");
        text_write(classes[i].name);
    }

    gotoxy(0, 9);  text_write("ROLE  ");
    text_write(role_tips[class_select_cursor]);
    gotoxy(0, 10); text_write("A ");
    text_write(primary_tips[class_select_cursor]);
    gotoxy(0, 11); text_write("B ");
    text_write(signature_tips[class_select_cursor]);
    gotoxy(0, 12); text_write("TRAIT ");
    text_write(trait_tips[class_select_cursor]);

    write_stats(c);
    {
        const char *name = c->name;
        u8 n = 0;
        while (name[n]) n++;
        class_select_name_len = n;
    }

    gotoxy(0, 16);
    text_write(class_select_easy_mode ? "EASY MORE HP FEW HEX"
                                      : "NORMAL  SEL FOR EASY");
    gotoxy(1, 17); text_write("A CHOOSE   B BACK");
    class_select_attr_prepare();
    class_select_attr_phase = 1;
}

static void refresh(void) {
    render();
    update_preview();
    cache_and_arm_palettes();
}

void class_select_enter(void) {
    DISPLAY_OFF;
    VBK_REG = 0;

    font_init();
    { font_t f = font_load(font_min); font_set(f); }

    // Class metasprites + cursor star for the live preview
    tiles_load_all_class_sprites();
    tiles_load_fx_sprites();

    class_select_cursor = 0;
    class_select_easy_mode = 0;
    render();
    update_preview();
    cache_and_arm_palettes();

    SHOW_SPRITES;
    SHOW_BKG;
    DISPLAY_ON;
}

void class_select_exit(void) {
    // Park preview + cursor sprites and stop palette bursts so the next
    // screen's palettes are not overwritten mid-VBlank.
    move_sprite(0, 0, 0); move_sprite(1, 0, 0);
    move_sprite(2, 0, 0); move_sprite(3, 0, 0);
    move_sprite(4, 0, 0);
    class_select_attr_phase = 0;
    class_select_pal_steps = 0;
    class_select_vbl_work = 0;
}

screen_id_t class_select_tick(u8 keys, u8 pressed) {
    keys;
    // Queued attribute/palette VBlank work. loop_run calls this tick right
    // after input_poll(), still at the top of the blank. Skip on A/B: that
    // frame leaves the screen (and A seeds the run) exactly like main.
    if (class_select_vbl_work && !(pressed & (J_A | J_B)))
        class_select_vblank_step();
    if (pressed & J_UP) {
        if (class_select_cursor == 0)
            class_select_cursor = (u8)(N_CLASSES - 1);
        else
            class_select_cursor--;
        refresh();
        sfx_play(SFX_HIT);          // soft move blip
    } else if (pressed & J_DOWN) {
        class_select_cursor++;
        if (class_select_cursor >= N_CLASSES) class_select_cursor = 0;
        refresh();
        sfx_play(SFX_HIT);
    }

    if (pressed & J_SELECT) {
        class_select_easy_mode = class_select_easy_mode ? 0 : 1;
        refresh();
        sfx_play(SFX_COIN);
    }

    if (pressed & J_A) {
        sfx_play(SFX_COIN);         // confirm
        player_init_from_class(class_select_cursor);
        return SCREEN_RUN_INIT;
    }
    if (pressed & J_B) {
        sfx_play(SFX_HURT);         // cancel
        return SCREEN_TITLE;
    }
    return SCREEN_SELF;
}

void class_select_draw(void) {
    // No per-frame redraw; render() runs on cursor change only.
}
