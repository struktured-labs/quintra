//! Content registry — collects all defined content for validation + codegen.

use crate::stage::N_STAGES;
use crate::{Biome, Class, Enemy, Item, RoomTemplate, StageTheme, ZeldaOverworldBiome};

#[derive(Clone, Debug, Default)]
pub struct Registry {
    pub classes:        Vec<Class>,
    pub items:          Vec<Item>,
    pub enemies:        Vec<Enemy>,
    pub biomes:         Vec<Biome>,
    pub zelda_overworlds: Vec<ZeldaOverworldBiome>,
    pub room_templates: Vec<RoomTemplate>,
    pub stages:         Vec<StageTheme>,
}

impl Registry {
    pub fn new() -> Self { Self::default() }

    pub fn add_class(&mut self, c: Class)        -> &mut Self { self.classes.push(c); self }
    pub fn add_item(&mut self, i: Item)          -> &mut Self { self.items.push(i); self }
    pub fn add_enemy(&mut self, e: Enemy)        -> &mut Self { self.enemies.push(e); self }
    pub fn add_biome(&mut self, b: Biome)        -> &mut Self { self.biomes.push(b); self }
    pub fn add_zelda_overworld(&mut self, z: ZeldaOverworldBiome) -> &mut Self {
        self.zelda_overworlds.push(z);
        self
    }
    pub fn add_room(&mut self, r: RoomTemplate)  -> &mut Self { self.room_templates.push(r); self }
    pub fn add_stage(&mut self, s: StageTheme)   -> &mut Self { self.stages.push(s); self }

    /// Validate every entry + check cross-references resolve.
    pub fn validate(&self) -> Result<(), Vec<String>> {
        let mut errs = Vec::new();

        for c in &self.classes        { if let Err(e) = c.validate()        { errs.push(e); } }
        for i in &self.items          { if let Err(e) = i.validate()        { errs.push(e); } }
        for e_ in &self.enemies       { if let Err(e) = e_.validate()       { errs.push(e); } }
        for b in &self.biomes         { if let Err(e) = b.validate()        { errs.push(e); } }
        for z in &self.zelda_overworlds {
            if let Err(z_errs) = z.validate() {
                errs.extend(z_errs);
            }
        }
        for r in &self.room_templates { if let Err(e) = r.validate()        { errs.push(e); } }
        for s in &self.stages         { if let Err(e) = s.validate()        { errs.push(e); } }

        // Stage structure: the run is exactly N_STAGES themed stages, in order.
        if !self.stages.is_empty() {
            if self.stages.len() != N_STAGES {
                errs.push(format!("expected exactly {} stages, found {}",
                    N_STAGES, self.stages.len()));
            }
            for (i, s) in self.stages.iter().enumerate() {
                if s.id as usize != i {
                    errs.push(format!("stage at position {} has id {} (must be in order)",
                        i, s.id));
                }
            }
            // Difficulty must never regress as the run deepens
            for w in self.stages.windows(2) {
                if w[1].boss_hp_bonus < w[0].boss_hp_bonus {
                    errs.push(format!("stage {} boss hp {} < stage {} boss hp {} — \
                        difficulty regression", w[1].id, w[1].boss_hp_bonus,
                        w[0].id, w[0].boss_hp_bonus));
                }
            }
            // Stage rosters must reference real enemies
            if !self.enemies.is_empty() {
                let ids: std::collections::HashSet<u8> =
                    self.enemies.iter().map(|e| e.id.raw() as u8).collect();
                for s in &self.stages {
                    for &(eid, _) in s.enemy_pool {
                        if !ids.contains(&eid) {
                            errs.push(format!(
                                "stage {} enemy_pool references missing enemy {}",
                                s.id, eid));
                        }
                    }
                }
            }
        }

        // Cross-ref checks
        let item_ids: std::collections::HashSet<_> = self.items.iter().map(|i| i.id).collect();
        let enemy_ids: std::collections::HashSet<_> = self.enemies.iter().map(|e| e.id).collect();
        let biome_ids: std::collections::HashSet<_> = self.biomes.iter().map(|b| b.id).collect();
        let zelda_overworld_ids: std::collections::HashSet<_> =
            self.zelda_overworlds.iter().map(|z| z.id).collect();
        let room_ids: std::collections::HashSet<_> = self.room_templates.iter().map(|r| r.id).collect();

        for c in &self.classes {
            if !item_ids.contains(&c.starter_weapon) {
                errs.push(format!("class {} starter_weapon item {} not found",
                    c.id.raw(), c.starter_weapon.raw()));
            }
            if !item_ids.contains(&c.signature_active) {
                errs.push(format!("class {} signature_active item {} not found",
                    c.id.raw(), c.signature_active.raw()));
            }
        }

        for e in &self.enemies {
            for b in e.biomes {
                if !biome_ids.contains(b) && !zelda_overworld_ids.contains(b) {
                    errs.push(format!("enemy {} references missing biome {}",
                        e.id.raw(), b.raw()));
                }
            }
        }

        for b in &self.biomes {
            for (eid, _) in b.enemy_pool {
                if !enemy_ids.contains(eid) {
                    errs.push(format!("biome {} enemy_pool references missing enemy {}",
                        b.id.raw(), eid.raw()));
                }
            }
            for tid in b.room_template_pool {
                if !room_ids.contains(tid) {
                    errs.push(format!("biome {} room_template_pool references missing template {}",
                        b.id.raw(), tid.raw()));
                }
            }
        }

        for z in &self.zelda_overworlds {
            for tid in z.referenced_room_templates() {
                if !room_ids.contains(&tid) {
                    errs.push(format!(
                        "zelda_overworld {} references missing room template {}",
                        z.id.raw(),
                        tid.raw(),
                    ));
                }
            }
        }

        if errs.is_empty() { Ok(()) } else { Err(errs) }
    }

    pub fn n_classes(&self) -> usize        { self.classes.len() }
    pub fn n_items(&self) -> usize          { self.items.len() }
    pub fn n_enemies(&self) -> usize        { self.enemies.len() }
    pub fn n_biomes(&self) -> usize         { self.biomes.len() }
    pub fn n_zelda_overworlds(&self) -> usize { self.zelda_overworlds.len() }
    pub fn n_room_templates(&self) -> usize { self.room_templates.len() }
    pub fn n_stages(&self) -> usize         { self.stages.len() }
}
