// Shared entity OAM allocator body.
//
// The includer supplies ENTITY_DRAW_SX(e), ENTITY_DRAW_SY(e), and
// enemy_is_big16(e), plus locals `u8 i` and `u8 oam = 4`. This deliberately
// lives as one source fragment so the zero-cost one-screen renderer and the
// banked two-axis world renderer cannot drift apart.
entity_anim_counter++;
for (i = 0; i < MAX_ENTITIES; ++i) {
    // Rotate the 32 logical slots through the 36 non-player OAM entries.
    // When a crowded scanline or several 16x16 bodies exceed hardware OAM,
    // every entity receives display priority on following frames instead of
    // later-spawned bullets/enemies becoming permanently invisible.
    u8 slot = (u8)((i + (entity_anim_counter >> 1))
        & (MAX_ENTITIES - 1));
    entity_t *e = &entities[slot];
    u8 sx, sy, pal, flash;
    if (!(e->flags & EF_ACTIVE)) continue;
    // The route-following Serpent owns fixed OAM 4..31 through its dedicated
    // renderer. Leaving its head in this generic pass would recreate the old
    // sprite-swapped Colossus and overwrite the articulated body.
    if (serpent_tail_active && slot == serpent_head_index) continue;
    // EF_ON_SCREEN is authoritative in compact rooms, streaming fields, and
    // Shade limbo alike. Every enemy spawns with it; only camera streaming or
    // an authored vanish phase clears it.
    if (e->type == ENT_ENEMY && !(e->flags & EF_ON_SCREEN)) continue;
    sx = ENTITY_DRAW_SX(e);
    sy = ENTITY_DRAW_SY(e);
    pal = e->palette;
    flash = (e->type == ENT_ENEMY && e->ai_data[7]) ? 1 : 0;

    // 32x32 Colossi — 16 tiles, row-major 4x4
    if (e->type == ENT_ENEMY && e->ai_data[0] == ENEMY_STONE_SENTINEL
        && e->ai_data[3]) {
        u8 r, c, tile = e->sprite_tile;
        if (flash) e->ai_data[7]--;
        if (oam + 16 > 40) continue;
        for (r = 0; r < 4; ++r) {
            for (c = 0; c < 4; ++c) {
                set_sprite_tile(oam, tile);
                set_sprite_prop(oam, pal);
                if (flash && (e->ai_data[7] & 1)) move_sprite(oam, 0, 0);
                else move_sprite(oam, (u8)(sx + c * 8), (u8)(sy + r * 8));
                oam++; tile++;
            }
        }
        continue;
    }

    // 16x16 — mini-boss or bruiser, 2x2 tiles
    if (enemy_is_big16(e)) {
        u8 t = e->sprite_tile;
        if (flash) e->ai_data[7]--;
        if (oam + 4 > 40) continue;
        if (flash && (e->ai_data[7] & 1)) {
            move_sprite(oam, 0, 0);
            move_sprite((u8)(oam + 1), 0, 0);
            move_sprite((u8)(oam + 2), 0, 0);
            move_sprite((u8)(oam + 3), 0, 0);
        } else {
            set_sprite_tile(oam, t);
            set_sprite_tile((u8)(oam + 1), (u8)(t + 1));
            set_sprite_tile((u8)(oam + 2), (u8)(t + 2));
            set_sprite_tile((u8)(oam + 3), (u8)(t + 3));
            set_sprite_prop(oam, pal);
            set_sprite_prop((u8)(oam + 1), pal);
            set_sprite_prop((u8)(oam + 2), pal);
            set_sprite_prop((u8)(oam + 3), pal);
            move_sprite(oam, sx, sy);
            move_sprite((u8)(oam + 1), (u8)(sx + 8), sy);
            move_sprite((u8)(oam + 2), sx, (u8)(sy + 8));
            move_sprite((u8)(oam + 3), (u8)(sx + 8), (u8)(sy + 8));
        }
        oam += 4;
        continue;
    }

    // 8x8 — everything else (small enemies, projectiles, pickups, fx)
    if (oam >= 40) continue;
    if (flash) {
        e->ai_data[7]--;
        if (e->ai_data[7] & 0x01) continue;
    }
    set_sprite_tile(oam, e->sprite_tile);
    {
        u8 prop = pal;
        if (e->type == ENT_ENEMY && (entity_anim_counter & 0x10))
            prop |= S_FLIPX;
        if (e->type == ENT_PROJECTILE) {
            if (e->ai_data[4] & PROJ_VIS_FLIP_X) prop |= S_FLIPX;
            if (e->ai_data[4] & PROJ_VIS_FLIP_Y) prop |= S_FLIPY;
        }
        set_sprite_prop(oam, prop);
    }
    move_sprite(oam, sx, sy);
    oam++;
}
// Park only sprites that were occupied on the preceding frame. Room entry
// already clears slots 4..39, and active slots are overwritten above; hiding
// the entire unused tail every frame was 20-35 redundant OAM writes.
i = oam;
while (i < entity_oam_high) {
    move_sprite(i, 0, 0);
    i++;
}
entity_oam_high = oam;
