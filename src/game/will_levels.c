#pragma bank 25

#include <gb/gb.h>

#include "core/types.h"
#include "game/player.h"
#include "game/will_levels.h"
#include "game/will.h"
#include "game/picsean_vortex.h"
#include "game/enemy_ai.h"
#include "render/tiles.h"
extern u8 vortex_cels;
#include "audio/sfx.h"

static const u8 spend_tab[4]  = { 16, 24, 32, 40 };
static const u16 recast_tab[4] = { 180, 240, 300, 360 };
static const u16 xp_need[3]   = { 80, 160, 280 };

static u8 cap_up_notice;

u8 will_levels_clamp(u8 level) BANKED {
    if (level < MAXWILL_MIN) return MAXWILL_MIN;
    if (level > MAXWILL_MAX) return MAXWILL_MAX;
    return level;
}

u8 will_levels_art(void) BANKED {
    return will_levels_clamp(player.maxwill_level);
}

u8 will_levels_clock(void) BANKED {
    /* All five champions now have L1-L3 MAX arts, so charge and
       recast follow the unlocked cap. */
    return will_levels_art();
}

u8 will_levels_charge_spend(void) BANKED {
    return spend_tab[(u8)(will_levels_clock() - 1)];
}


u8 will_levels_picsean_drain(void) BANKED {
    u8 clock = player.maxwill_level;
    u8 spend;
    if (clock < MAXWILL_MIN) clock = MAXWILL_MIN;
    if (clock > MAXWILL_MAX) clock = MAXWILL_MAX;
    spend = spend_tab[(u8)(clock - 1)];
    while (will_charge_fraction >= spend) {
        will_charge_fraction = (u8)(will_charge_fraction - spend);
        if (++player.will_charge >= WILL_NEXT_MAX) return 1;
    }
    return 0;
}

u16 will_levels_recast_frames(void) BANKED {
    return recast_tab[(u8)(will_levels_clock() - 1)];
}

void will_levels_init_run(void) BANKED {
    player.maxwill_level = MAXWILL_MIN;
    player.maxwill_xp = 0;
    cap_up_notice = 0;
}

void will_levels_on_load(void) BANKED {
    player.maxwill_level = will_levels_clamp(player.maxwill_level);
    if (player.maxwill_level >= MAXWILL_MAX) player.maxwill_xp = 0;
}

static void maybe_cap_up(void) {
    if (player.maxwill_level >= MAXWILL_MAX) {
        player.maxwill_xp = 0;
        return;
    }
    while (player.maxwill_level < MAXWILL_MAX) {
        u16 need = xp_need[(u8)(player.maxwill_level - 1)];
        if (player.maxwill_xp < need) return;
        player.maxwill_xp = (u16)(player.maxwill_xp - need);
        player.maxwill_level++;
        cap_up_notice = 1;
    }
    if (player.maxwill_level >= MAXWILL_MAX) player.maxwill_xp = 0;
    if (cap_up_notice) {
        sfx_play(SFX_WILL);
        will_levels_hud_pips();
    }
}

void will_levels_on_kill(u8 kind) BANKED {
    u8 add;
    if (player.maxwill_level >= MAXWILL_MAX) return;
    add = (kind == 2) ? 8 : (kind == 1) ? 2 : 1;
    player.maxwill_xp = (u16)(player.maxwill_xp + add);
    maybe_cap_up();
}

void will_levels_on_max_cast(void) BANKED {
    /* +2 use-XP only on a committed dump of the current cap. */
    if (player.maxwill_level >= MAXWILL_MAX) return;
    player.maxwill_xp = (u16)(player.maxwill_xp + 2);
    maybe_cap_up();
}

void will_levels_hud_pips(void) BANKED {
    /* Mastery stand-in: a digit in the free column between MP and the
       Will bar (true 4-pip tiles are a follow-up; no new 2bpp sheet
       in this PR). Column 11 is blank on the standard 20-tile lane. */
    u8 row[1];
    u8 lv = will_levels_art();
    row[0] = (u8)(HUD_DIGIT_0 + lv);
    VBK_REG = 0;
    set_win_tiles(11, 0, 1, 1, row);
    (void)cap_up_notice;
}

void will_levels_vortex_setup(u8 *rmax, u8 *life, u8 *grow,
    u8 *mul, u8 *heavy) BANKED
{
    static const u8 rcap[4]  = { 48, 112, 176, 240 };
    static const u8 life_t[4] = { 24, 44, 64, 84 };
    static const u8 grow_t[4] = { 18, 36, 54, 72 };
    static const u8 mul_t[4]  = { 77, 136, 197, 0 };
    static const u8 heavy_t[4] = { 2, 3, 5, 6 };
    u8 lv = will_levels_art();
    lv = will_levels_clamp(lv);
    *life = life_t[(u8)(lv - 1)];
    *grow = grow_t[(u8)(lv - 1)];
    *mul = mul_t[(u8)(lv - 1)];
    *heavy = heavy_t[(u8)(lv - 1)];
    if (*rmax > rcap[(u8)(lv - 1)]) *rmax = rcap[(u8)(lv - 1)];
    vortex_cels = (lv >= 4) ? 12 : (u8)((u8)(lv + 1) << 1);
}

void will_levels_vortex_trim_oam(u8 *seg, u8 level) BANKED {
    /* Pack kept cels into the tail of the 12-cel buffer so the
       unchanged L4 draw path (OAM 24-35) places L1 in 32-35, L2 in
       30-35, and L3 in 28-35. L4 never calls this. */
    u8 cels, arms, s, d, off, k;
    if (level < 1) level = 1;
    if (level >= 4) return;
    cels = (u8)((u8)(level + 1) << 1);
    arms = (level <= 1) ? 4 : level;
    d = 0;
    for (s = 0; s < 12 && d < cels; s++) {
        if ((u8)(s & 3) < arms) {
            if (d != s) {
                for (k = 0; k < 4; k++)
                    seg[(u8)(d * 4 + k)] = seg[(u8)(s * 4 + k)];
            }
            d++;
        }
    }
    off = (u8)(12 - d);
    if (off) {
        s = d;
        while (s) {
            s--;
            for (k = 0; k < 4; k++)
                seg[(u8)((s + off) * 4 + k)] = seg[(u8)(s * 4 + k)];
        }
        for (s = 0; s < off; s++)
            seg[(u8)(s * 4)] = 0;
    }
    vortex_cels = cels;
}

void room_draw_overlays(void) BANKED {
    if (serpent_tail_active) serpent_draw();
    if (cinder_pack_active) cinder_draw();
    if (picsean_vortex_ticks) picsean_vortex_draw();
}
