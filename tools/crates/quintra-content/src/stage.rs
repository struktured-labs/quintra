//! Stage themes — the nine dungeon looks (palettes + names).
//!
//! Each stage owns four BG palettes (floor / wall / crystal / door), the
//! large-boss OBJ tint, and its display name. The cracked-wall palette is
//! global (the "shoot me" signal must read the same in every stage).
//!
//! Invariants enforced at `cargo build`:
//!   - exactly `N_STAGES` themes, ids 0..N in order
//!   - every channel fits 5 bits (0-31)
//!   - names fit the PACK line and the GB font (A-Z, digits, space)

/// One CGB color, 5 bits per channel. Encoded to BGR555 at emit time.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Rgb5(pub u8, pub u8, pub u8);

impl Rgb5 {
    pub fn validate(self) -> Result<(), String> {
        match self.0 <= 31 && self.1 <= 31 && self.2 <= 31 {
            true => Ok(()),
            false => Err(format!("Rgb5({},{},{}) channel out of 5-bit range",
                self.0, self.1, self.2)),
        }
    }

    /// GB hardware format: bits 0-4 red, 5-9 green, 10-14 blue.
    pub fn to_bgr555(self) -> u16 {
        (self.0 as u16) | ((self.1 as u16) << 5) | ((self.2 as u16) << 10)
    }
}

/// The number of stages in a run — the game's structure constant.
pub const N_STAGES: usize = 9;

/// Longest stage name the PACK screen line fits (col 1..19).
pub const MAX_STAGE_NAME: usize = 15;

#[derive(Debug, Clone)]
pub struct StageTheme {
    pub id: u8,
    pub name: &'static str,
    /// BG palettes, 4 colors each (dark -> light)
    pub floor:   [Rgb5; 4],
    pub wall:    [Rgb5; 4],
    pub crystal: [Rgb5; 4],
    pub door:    [Rgb5; 4],
    /// Large-boss OBJ tint: [transparent, rim, body-dark, glow]
    pub boss:    [Rgb5; 4],
    /// Large-boss stats: added on top of the base enemy entry.
    /// Registry enforces hp monotonically non-decreasing across stages.
    pub boss_hp_bonus:  u8,
    pub boss_dmg_bonus: u8,
    /// Mini-boss silhouette: 0 = Sentinel, 1 = Orc, 2 = Skeleton. One
    /// value consumed by BOTH the art loader and the palette pick — the
    /// two hand-written C copies used to have to agree by comment.
    pub mb_variant: u8,
}

pub const MB_VARIANTS: u8 = 3;

impl StageTheme {
    pub fn validate(&self) -> Result<(), String> {
        if self.name.is_empty() || self.name.len() > MAX_STAGE_NAME {
            return Err(format!("stage {} name {:?} must be 1..={} chars",
                self.id, self.name, MAX_STAGE_NAME));
        }
        if !self.name.chars().all(|c| c.is_ascii_uppercase()
            || c.is_ascii_digit() || c == ' ') {
            return Err(format!("stage {} name {:?} must be A-Z / 0-9 / space \
                (GB min-font)", self.id, self.name));
        }
        for pal in [&self.floor, &self.wall, &self.crystal, &self.door, &self.boss] {
            for c in pal {
                c.validate().map_err(|e| format!("stage {}: {}", self.id, e))?;
            }
        }
        if self.mb_variant >= MB_VARIANTS {
            return Err(format!("stage {} mb_variant {} out of range (0..{})",
                self.id, self.mb_variant, MB_VARIANTS));
        }
        Ok(())
    }
}
