// Shared entity OAM allocator body.
//
// The includer supplies ENTITY_DRAW_SX(e), ENTITY_DRAW_SY(e), and
// enemy_is_big16(e), plus locals `u8 i` and `u8 oam = 4`. This deliberately
// lives as one source fragment so the zero-cost one-screen renderer and the
// banked two-axis world renderer cannot drift apart.
entity_anim_counter++;
if (large_boss_index != 255) oam = large_boss_draw(oam);
/* Limb quads own OAM 4..23. Projectiles start after them, and the quads are
   written again after this pass so a projectile hide cannot punch a hole. */
if (hexa_boss_active && oam < 24) oam = 24;
for (i = 0; i < MAX_ENTITIES; ++i) {
    // Rotate the 32 logical slots through the 36 non-player OAM entries.
    // When a crowded scanline or several 16x16 bodies exceed hardware OAM,
    // every entity receives display priority on following frames instead of
    // later-spawned bullets/enemies becoming permanently invisible.
    // A pointer step here was measured slower than this multiply on the
    // inactive-slot scan, so the index stays.
    u8 slot = (u8)((i + (entity_anim_counter >> 1))
        & (MAX_ENTITIES - 1));
    entity_t *e = &entities[slot];
    u8 sx, sy, pal, flash;
    if (!(e->flags & EF_ACTIVE)) continue;
    // The route-following Serpent owns fixed OAM 4..31 through its dedicated
    // renderer. Leaving its head in this generic pass would recreate the old
    // sprite-swapped Colossus and overwrite the articulated body.
    if (serpent_tail_active && slot == serpent_head_index) continue;
    // The Ember boss likewise owns five 16x8 pack bodies or one 32x16 Rex.
    // Its logical entity remains the current armor/vent collision anchor but
    // must never leak the legacy generic 32x32 picture into the formation.
    if (cinder_pack_active && slot == cinder_boss_index) continue;
    // EF_ON_SCREEN is authoritative in compact rooms, streaming fields, and
    // Shade limbo alike. Every enemy spawns with it; only camera streaming or
    // an authored vanish phase clears it.
    if (e->type == ENT_ENEMY && !(e->flags & EF_ON_SCREEN)) continue;
    sx = ENTITY_DRAW_SX(e);
    sy = ENTITY_DRAW_SY(e);
    pal = e->palette;
    if (e->type == ENT_PROJECTILE && ((e->flags & EF_BOSS_PROJECTILE)
        || e->ai_data[6] >= PROJ_AUX_HOOKSHOT)) {
        oam = boss_projectile_draw(e, oam, sx, sy);
        continue;
    }
    if (e->type == ENT_ENEMY && enemy_status_kind[slot] != QSTATUS_NONE
        && (entity_anim_counter & 0x08))
        pal = status_enemy_palette_prop(slot);
    flash = (e->type == ENT_ENEMY && e->ai_data[7]) ? 1 : 0;

    // Return champions use a 24x24 cloak around their 14x14 collision body.
    if (e->type == ENT_ENEMY
        && ((e->ai_data[0] == ENEMY_STONE_SENTINEL && e->ai_data[3])
            || (room_return_echo_kind >= 4 && slot == room_encounter_target))) {
        if (slot == large_boss_index) continue;
        if (hexa_boss_active && e->ai_data[2] == HEXA_STAGE) continue;
        u8 side = e->ai_data[0] == ENEMY_STONE_SENTINEL ? 4 : 3;
        u8 tile = side == 3 ? SPR_BOSS_BIG : e->sprite_tile;
        if (side == 3) { sx -= 4; sy -= 8; }
        if (flash) e->ai_data[7]--;
        if (oam + (side == 3 ? 9 : 16) > 40) continue;
        oam = colossus_oam_draw(oam, sx, sy, tile, pal, side, e,
            (u8)(flash && (e->ai_data[7] & 1)));
        continue;
    }

    // 16x16 — civic resident, mini-boss, or bruiser; 2x2 tiles. Residents
    // grow around their old 8x8 feet-anchor, so authored town positions and
    // proximity dialogue remain stable while the silhouette doubles in size.
    if (enemy_is_big16(e)) {
        u8 t = e->sprite_tile;
        u8 bx = sx, by = sy;
        if (e->type == ENT_PICKUP) {
            bx = (u8)(bx - 4);
            by = (u8)(by - 8);
        }
        if (oam + 4 > 40) continue;
        if (e->type == ENT_ENEMY && e->ai_data[0] == ENEMY_FACET_RAM) {
            facet_ram_draw(e, oam, bx, by, pal);
            oam += 4;
            continue;
        }
        if (flash) e->ai_data[7]--;
        if (flash && (e->ai_data[7] & 1)) {
            // move_sprite(n, 0, 0) writes Y and X only.
            OAM_item_t *it = &shadow_OAM[oam];
            it[0].y = 0; it[0].x = 0;
            it[1].y = 0; it[1].x = 0;
            it[2].y = 0; it[2].x = 0;
            it[3].y = 0; it[3].x = 0;
        } else {
            OAM_item_t *it = &shadow_OAM[oam];
            u8 bx8 = (u8)(bx + 8);
            u8 by8 = (u8)(by + 8);
            it->y = by;  it->x = bx;  it->tile = t;           it->prop = pal; ++it;
            it->y = by;  it->x = bx8; it->tile = (u8)(t + 1); it->prop = pal; ++it;
            it->y = by8; it->x = bx;  it->tile = (u8)(t + 2); it->prop = pal; ++it;
            it->y = by8; it->x = bx8; it->tile = (u8)(t + 3); it->prop = pal;
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
    {
        OAM_item_t *it = &shadow_OAM[oam];
        u8 prop = pal;
        if (e->type == ENT_ENEMY && (entity_anim_counter & 0x10))
            prop |= S_FLIPX;
        if (e->type == ENT_PROJECTILE) {
            if (e->ai_data[4] & PROJ_VIS_FLIP_X) prop |= S_FLIPX;
            if (e->ai_data[4] & PROJ_VIS_FLIP_Y) prop |= S_FLIPY;
        }
        it->y = sy;
        it->x = sx;
        it->tile = e->sprite_tile;
        it->prop = prop;
    }
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
if (hexa_boss_active) hexa_boss_draw(4);
