// Ordinary-sprite fast path for the shared entity OAM allocator.
//
// Included at file scope (after enemy_is_big16) by both renderers, which
// supply the same ENTITY_DRAW_SX/SY macros. The general loop body in
// entity_draw_core.h keeps ~20 live values and SDCC spills the entity
// pointer on every field access, so each plain 8x8 effect, shot or small
// enemy cost ~2.7k clocks to place. This leaf handles exactly those plain
// cases with the identical OAM bytes, and returns 0xFF for everything with
// special drawing (boss shots, flashes, status tints, 16x16 bodies,
// champions, pickups) so the general path still owns them unchanged.
static u8 entity_draw_fast(entity_t *e, u8 slot, u8 oam) {
    u8 prop = e->palette;
    u8 t = e->type;
    if (t == ENT_FX) {
        // Effects have no flash, tint or large form.
    } else if (t == ENT_PROJECTILE) {
        u8 vis;
        if (e->flags & EF_BOSS_PROJECTILE) return 0xFF;
        if (e->ai_data[6] >= PROJ_AUX_HOOKSHOT) return 0xFF;
        vis = e->ai_data[4];
        if (vis & PROJ_VIS_FLIP_X) prop |= S_FLIPX;
        if (vis & PROJ_VIS_FLIP_Y) prop |= S_FLIPY;
    } else if (t == ENT_ENEMY) {
        if (!(e->flags & EF_ON_SCREEN)) return oam;   // asleep: not drawn
        if (e->ai_data[7]) return 0xFF;               // hit flash
        if (enemy_status_kind[slot] != QSTATUS_NONE) return 0xFF;
        if (room_return_echo_kind >= 4 && slot == room_encounter_target)
            return 0xFF;
        if (enemy_is_big16(e)) return 0xFF;           // includes Sentinel
    } else {
        return 0xFF;
    }
    if (oam >= entity_oam_cap) return oam;
    {
        OAM_item_t *it = &shadow_OAM[oam];
        it->y = ENTITY_DRAW_SY(e);
        it->x = ENTITY_DRAW_SX(e);
        it->tile = e->sprite_tile;
        it->prop = prop;
    }
    return (u8)(oam + 1);
}
