//! Named ID constants for content cross-references. Keeps the actual
//! type definitions readable.

use quintra_content::{
    BiomeId, BossId, ClassId, DropTableId, EnemyId, ItemId, MusicRef,
    PaletteRef, PerkId, RoomTemplateId, SpriteRef, TilemapId, TilesetRef,
};

// ----- Classes
pub const CLASS_WOLFKIN: ClassId = ClassId::new(0);
pub const CLASS_SAURAN:  ClassId = ClassId::new(1);
pub const CLASS_CORVIN:  ClassId = ClassId::new(2);
pub const CLASS_PICSEAN: ClassId = ClassId::new(3);
pub const CLASS_VESPINE: ClassId = ClassId::new(4);

// ----- Items (weapons 0-9, actives 10-19, passives 20+)
pub const ITEM_CLAW_COMBO:   ItemId = ItemId::new(0);
pub const ITEM_TAIL_SPIKE:   ItemId = ItemId::new(1);
pub const ITEM_FEATHER_SHURI:ItemId = ItemId::new(2);
pub const ITEM_BUBBLE_BOLT:  ItemId = ItemId::new(3);
pub const ITEM_STINGER:      ItemId = ItemId::new(4);

pub const ITEM_HOWL:         ItemId = ItemId::new(10);
pub const ITEM_STONESKIN:    ItemId = ItemId::new(11);
pub const ITEM_MURDER:       ItemId = ItemId::new(12);
pub const ITEM_TIDAL_WAVE:   ItemId = ItemId::new(13);
pub const ITEM_SWARM:        ItemId = ItemId::new(14);

pub const ITEM_IRON_HEART:   ItemId = ItemId::new(20);   // +2 HP
pub const ITEM_SPEED_RING:   ItemId = ItemId::new(21);   // +1 SPD
pub const ITEM_POWER_STONE:  ItemId = ItemId::new(22);   // +1 ATK
pub const ITEM_TOUGH_SKIN:   ItemId = ItemId::new(23);   // +1 DEF
pub const ITEM_LUCKY_COIN:   ItemId = ItemId::new(24);   // +2 LCK
pub const ITEM_MANA_GEM:     ItemId = ItemId::new(25);   // +2 MP
pub const ITEM_WARD_CHARM:   ItemId = ItemId::new(26);   // +1 DEF +1 LCK
pub const ITEM_SWIFT_FANG:   ItemId = ItemId::new(27);   // +1 SPD +1 ATK
pub const ITEM_HUNTERS_EYE:  ItemId = ItemId::new(28);   // +3 LCK
pub const ITEM_BLOOD_SIGIL:  ItemId = ItemId::new(29);   // +1 ATK +1 HP
pub const ITEM_RIFT_FLAIL:   ItemId = ItemId::new(30);   // rare physical weapon swap
pub const ITEM_ASTRAL_SPEAR: ItemId = ItemId::new(31);   // rare long-reach weapon swap

// ----- Enemies
pub const ENEMY_BLUE_CRAWLER:    EnemyId = EnemyId::new(0);
pub const ENEMY_STONE_SENTINEL:  EnemyId = EnemyId::new(1);    // Crystal Caverns boss
pub const ENEMY_HORNET:          EnemyId = EnemyId::new(2);    // fast flyer
pub const ENEMY_SKELETON:        EnemyId = EnemyId::new(3);    // chaser
pub const ENEMY_ORC:             EnemyId = EnemyId::new(4);    // tank
pub const ENEMY_WISP:            EnemyId = EnemyId::new(5);    // ranged shooter
pub const ENEMY_BOMBER:          EnemyId = EnemyId::new(6);    // walker; detonates on death
pub const ENEMY_SHADE:           EnemyId = EnemyId::new(7);    // teleporting stalker
pub const ENEMY_WARLOCK:         EnemyId = EnemyId::new(8);    // fan-fire caster
pub const ENEMY_ROPE:            EnemyId = EnemyId::new(9);    // snake: wander then bee-line charge
pub const ENEMY_SENTRY:          EnemyId = EnemyId::new(10);   // stationary rotating turret
pub const ENEMY_FOLDING_STAR:    EnemyId = EnemyId::new(11);   // diagonal echo replicator
pub const ENEMY_FLUTTERBAT:      EnemyId = EnemyId::new(12);   // rest/flutter/dart flyer
pub const ENEMY_GLOAM_LEECH:     EnemyId = EnemyId::new(13);   // attaches and drains life
pub const ENEMY_CINDER_MAW:      EnemyId = EnemyId::new(14);   // Ember Depths area-denial caster
pub const ENEMY_RIFT_OOZE:       EnemyId = EnemyId::new(15);   // splits into two crawler fragments
pub const ENEMY_MIRROR_MOTH:     EnemyId = EnemyId::new(16);   // mirrors hero motion, fires reflected bolts
pub const ENEMY_MIRE_SPORE:      EnemyId = EnemyId::new(17);   // proximity-armed radial burst mine
pub const ENEMY_ECHO_GUARD:      EnemyId = EnemyId::new(18);   // blocks one hit, counters, then opens
pub const ENEMY_RUNE_LANTERN:    EnemyId = EnemyId::new(19);   // drifting four-lane ring caster
pub const ENEMY_DREAD_BELL:      EnemyId = EnemyId::new(20);   // late-stage eight-way peal caster
pub const ENEMY_RIFT_WARDEN:     EnemyId = EnemyId::new(21);   // late-stage five-way lane breaker
pub const ENEMY_PRISM_SKITTER:   EnemyId = EnemyId::new(22);   // orbiting late-stage lane splitter
pub const ENEMY_DUSK_MIDGE:      EnemyId = EnemyId::new(23);   // fast late-game fan-fire harrier
pub const ENEMY_SUNWHEEL:        EnemyId = EnemyId::new(24);   // Golden Temple orbiting lane shaper
pub const ENEMY_CINDER_KITE:     EnemyId = EnemyId::new(25);   // Ember fast fan-fire harrier
pub const ENEMY_BOG_TOAD:        EnemyId = EnemyId::new(26);   // Toxic Mire telegraphed pounce bruiser

// ----- Biomes
pub const BIOME_CRYSTAL_CAVERNS: BiomeId = BiomeId::new(0);
pub const BIOME_ZELDA_OVERWORLD: BiomeId = BiomeId::new(1);

// ----- Bosses (placeholder — boss data currently lives in enemies table)
pub const BOSS_NONE:             BossId = BossId::new(0);
pub const BOSS_STONE_SENTINEL:   BossId = BossId::new(1);

// ----- Rooms
pub const ROOM_SMALL_EMPTY: RoomTemplateId = RoomTemplateId::new(0);

// ----- Drop tables (placeholder slot 0 = small-coin)
pub const DROP_SMALL_COIN: DropTableId = DropTableId::new(0);

// ----- Perks (engine-recognized; runtime hooks per perk-id)
pub const PERK_NONE:                PerkId = PerkId::new(0);
pub const PERK_MOVE_SPEED_PLUS_20:  PerkId = PerkId::new(1);  // Wolfkin
pub const PERK_HP_PLUS_2_SLOW_REGEN: PerkId = PerkId::new(2); // Sauran
pub const PERK_SEE_HP_REVEAL:       PerkId = PerkId::new(3);  // Corvin
pub const PERK_MP_REGEN_SWIM:       PerkId = PerkId::new(4);  // Picsean
pub const PERK_POISON_SYNERGY:      PerkId = PerkId::new(5);  // Vespine

// ----- Palettes / sprites / tilesets / music (engine-side index)
pub const OBJ_PAL_WOLFKIN:    PaletteRef = PaletteRef::new(1);
pub const OBJ_PAL_CRAWLER:    PaletteRef = PaletteRef::new(3);
pub const OBJ_PAL_BONE:       PaletteRef = PaletteRef::new(0);
pub const OBJ_PAL_RED:        PaletteRef = PaletteRef::new(4);
pub const OBJ_PAL_GOLD:       PaletteRef = PaletteRef::new(5);
pub const OBJ_PAL_MAGIC:      PaletteRef = PaletteRef::new(6);
pub const OBJ_PAL_GREEN:      PaletteRef = PaletteRef::new(7);
pub const OBJ_PAL_ITEM_GOLD:  PaletteRef = PaletteRef::new(3);
pub const OBJ_PAL_SAURAN:     PaletteRef = PaletteRef::new(1);    // reuses pal 1 (green tint at runtime)
pub const OBJ_PAL_CORVIN:     PaletteRef = PaletteRef::new(1);
pub const OBJ_PAL_PICSEAN:    PaletteRef = PaletteRef::new(1);
pub const OBJ_PAL_VESPINE:    PaletteRef = PaletteRef::new(1);
pub const BG_PAL_CAVERN_BASE: PaletteRef = PaletteRef::new(0);
pub const BG_PAL_CAVERN_DEC:  PaletteRef = PaletteRef::new(1);
pub const BG_PAL_CAVERN_ALT:  PaletteRef = PaletteRef::new(2);
pub const BG_PAL_CAVERN_HI:   PaletteRef = PaletteRef::new(3);

pub const SPRITE_WOLFKIN:     SpriteRef = SpriteRef::new(0);
// Enemy SpriteRef values are the actual OBJ tile slots consumed by runtime.
// Keep these aligned with render/tiles.h; content validation constrains them
// to the 0..127 hardware OBJ tile range.
pub const SPRITE_CRAWLER:     SpriteRef = SpriteRef::new(20);
pub const SPRITE_HORNET:      SpriteRef = SpriteRef::new(21);
pub const SPRITE_SKELETON:    SpriteRef = SpriteRef::new(22);
pub const SPRITE_SENTINEL:    SpriteRef = SpriteRef::new(24);
pub const SPRITE_WISP:        SpriteRef = SpriteRef::new(34);
pub const SPRITE_SHADE:       SpriteRef = SpriteRef::new(37);
pub const SPRITE_ROPE:        SpriteRef = SpriteRef::new(39);
pub const SPRITE_ORC:         SpriteRef = SpriteRef::new(56);
pub const SPRITE_BOMBER:      SpriteRef = SpriteRef::new(60);
pub const SPRITE_WARLOCK:     SpriteRef = SpriteRef::new(64);
pub const SPRITE_SENTRY:      SpriteRef = SpriteRef::new(68);
pub const SPRITE_FOLD_STAR:   SpriteRef = SpriteRef::new(72);
pub const SPRITE_FLUTTERBAT:  SpriteRef = SpriteRef::new(73);
pub const SPRITE_GLOAM_LEECH: SpriteRef = SpriteRef::new(74);
pub const SPRITE_CINDER_MAW:  SpriteRef = SpriteRef::new(75);
pub const SPRITE_RIFT_OOZE:   SpriteRef = SpriteRef::new(76);
pub const SPRITE_MIRROR_MOTH: SpriteRef = SpriteRef::new(77);
pub const SPRITE_MIRE_SPORE:  SpriteRef = SpriteRef::new(78);
pub const SPRITE_ECHO_GUARD:  SpriteRef = SpriteRef::new(80);
pub const SPRITE_RUNE_LANTERN: SpriteRef = SpriteRef::new(124);
// Slot 125 is a dungeon-only multiplex: combat rooms load Dread Bell art;
// merchant/town rooms retain the proximity callout in that slot.
pub const SPRITE_DREAD_BELL:    SpriteRef = SpriteRef::new(125);
// Dungeon combat may reuse the merchant-only sale-tag tile. Shop/town rooms
// never spawn a Rift Warden and keep this slot's gold marker intact.
pub const SPRITE_RIFT_WARDEN:   SpriteRef = SpriteRef::new(81);
// Dungeon combat reuses the town-only elder tile; towns never spawn hostile
// Skitters, so the additional enemy does not consume a permanent OBJ slot.
pub const SPRITE_PRISM_SKITTER: SpriteRef = SpriteRef::new(69);
// Town apothecaries never share a room with dungeon hostiles, so combat can
// reuse their otherwise-resident tile without expanding the fixed OBJ atlas.
pub const SPRITE_DUSK_MIDGE:     SpriteRef = SpriteRef::new(79);
// Golden Temple never spawns Dusk Midges, so its combat-only Sunwheel can
// reclaim the same apothecary slot without expanding the fixed OBJ atlas.
pub const SPRITE_SUNWHEEL:       SpriteRef = SpriteRef::new(79);
// Ember Depths never shares a room with Sunwheels or Dusk Midges, so its
// Cinder Kite can use the same phase-safe apothecary slot.
pub const SPRITE_CINDER_KITE:    SpriteRef = SpriteRef::new(79);
// Toxic Mire never shares a combat room with Ember/Bloodmoon/Temple harriers,
// so its Bog Toad reclaims the same phase-safe apothecary OBJ slot.
pub const SPRITE_BOG_TOAD:       SpriteRef = SpriteRef::new(79);
pub const SPRITE_ITEM_CLAW:   SpriteRef = SpriteRef::new(2);
pub const SPRITE_ITEM_HOWL:   SpriteRef = SpriteRef::new(3);

// OBJ palette index for Stone Sentinel (loaded at room enter)
pub const OBJ_PAL_SENTINEL:   PaletteRef = PaletteRef::new(6);

pub const TILESET_CAVERN:     TilesetRef = TilesetRef::new(0);
pub const TILEMAP_SMALL_EMPTY: TilemapId = TilemapId::new(0);
pub const MUSIC_CAVERN:       MusicRef  = MusicRef::new(0);
