//! Typed ID newtypes. Opaque at runtime, validated at codegen.

use serde::{Deserialize, Serialize};

macro_rules! id_newtype {
    ($name:ident, $repr:ty, $doc:literal) => {
        #[doc = $doc]
        #[derive(Copy, Clone, PartialEq, Eq, Hash, Debug, Serialize, Deserialize, PartialOrd, Ord)]
        #[serde(transparent)]
        pub struct $name(pub $repr);

        impl $name {
            pub const fn new(v: $repr) -> Self { Self(v) }
            pub const fn raw(self) -> $repr { self.0 }
        }

        impl From<$repr> for $name {
            fn from(v: $repr) -> Self { Self(v) }
        }
    };
}

id_newtype!(ClassId,        u8,  "Class identifier (5 starters + future hidden)");
id_newtype!(ItemId,         u16, "Item identifier");
id_newtype!(EnemyId,        u8,  "Enemy identifier");
id_newtype!(BiomeId,        u8,  "Biome identifier");
id_newtype!(BossId,         u8,  "Boss identifier");
id_newtype!(RoomTemplateId, u16, "Room template identifier");
id_newtype!(PaletteRef,     u8,  "Palette slot (0-7 for BG, 0-7 for OBJ)");
id_newtype!(SpriteRef,      u8,  "Sprite tile-set reference");
id_newtype!(TilesetRef,     u8,  "BG tile-set reference");
id_newtype!(TilemapId,      u16, "Tilemap blob reference");
id_newtype!(MusicRef,       u8,  "Music track reference");
id_newtype!(DropTableId,    u8,  "Drop table reference");
id_newtype!(PerkId,         u8,  "Class passive perk reference (engine-recognized)");
