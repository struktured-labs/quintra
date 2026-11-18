# Elemental hero magic: B tap = attack spell, B hold = ward spell

Date: 2026-11-17. Status: approved to build by Carmelo ("respec it as genuine
FF Adventure style magic but elemental for each character ... or Sword of
Mana"; addenda: one homing spell, tap = offensive / hold = defensive, A+B
must still be a special, balance the whole kit). Replaces the five B
"signatures" (Howl, Stoneskin, Raven Mark, Undertow, Swarm) when the hero
power is the selected B item. Hookshot, Boomerang, Morningstar and Bombs keep
their press-to-use B behaviour.

## Why the old B is weak (measured on main 4614675c)

| Hero | Old B | Cost / CD | What it does | Problem |
|---|---|---|---|---|
| Wolfkin | Howl | free / 72f | 8 claw lanes (dmg p1+1+atk = 4), wipes hostile shots within 52px, 30f i-frames | Lanes are 18-tick melee arcs: almost never reaches anything Fang Stab does not already hit |
| Sauran | Stoneskin | free / 90f | 60f shot/body shield | Pure defence, no damage, no utility |
| Corvin | Raven Mark | free / 54f | One dart (hp 1) and +1 dmg on the marked foe for 3s | +1 on a 3-dmg feather; invisible payoff |
| Picsean | Undertow | free / 120f | 3 bubbles (dmg 4) + 100f shield | Slow 2px/f bubbles, shares look with A |
| Vespine | Swarm | free / 72f | 6 aimed stings over 1.6s (dmg 4) | Barely distinct from held A (6 dmg every 20f) |

None used MP, none has an element payoff beyond what A already does, and
none touches the room. They are tactical verbs, not magic.

## Sources: how Mana magic feels

- Final Fantasy Adventure (GB 1991) / Adventures of Mana: B casts the
  equipped spell for MP. Fire 1 MP, a fireball that **homes on a nearby
  monster**. Ice 2 MP, an icicle **steered with the D-pad** after release,
  turns the target into a snowman (frozen). Lit 2 MP, straight thunderbolt.
  Cure 2 MP heals; Heal 1 MP cures status. Spell power scales with the Will
  gauge at cast time. Fire-type foes resist Fire, etc.
- Sword of Mana (GBA): each spirit has a support and an attack spell. Tap
  = support (3 MP), hold until the spirit icon revolves around the hero,
  release = attack (6 MP, twice the cost). Support spells are short timed
  buffs (PowerUp, D-Fence, SpeedUp, BubbleBoat) or HealingLight. Every
  attack spell has a side status (FireMan, SnowMan, Numb, Petrify, Sleep).
- **Deviation, on purpose:** Carmelo asked for tap = offensive, hold =
  defensive. We follow that. The attack is the frequent verb and must be
  low-latency; the ward is the deliberate one. The SoM "spirit revolves
  around you" charge tell is kept for the hold.

## Input contract (unambiguous)

Only when the hero power is the selected B item (`active_item >= 10`);
other B items keep their press-to-use path (`secondary_fire`).

1. B press with A up starts a charge (`magic_hold` counts frames). B press
   while A is held is the A+B chord, exactly as today; no charge starts.
2. A pressed or held at any time during a charge cancels it silently; the
   chord path in room.c (Oath / Spirit Convergence) runs that same frame and
   no spell casts. So B-then-A and A-then-B are both always A+B. The chord
   runs before `magic_input` in the room tick, so it always wins.
3. Release B with `magic_hold < 24` (0.40 s): **attack spell**.
4. Release with `magic_hold >= 24`: **ward spell**.
5. Charge tell (SoM's "spirit revolves around you"): from frame 6 an element
   mote circles the hero (one FX every 4 frames, 14 px ring, 45 deg per
   step). At frame 24 a 4-mote ring and a two-note "ready" ping; motes keep
   orbiting while held. When the ward is unaffordable, on cooldown or still
   live, the motes are grey and the ping is the refusal sound.
6. A charge does not survive a screen change: a gap of more than 8 frames
   (Pack, map, vignette, room seam) or Mute cancels it.
7. No cast and nothing spent when: Mute, too little MP, spell on cooldown,
   or (wards) a ward still live or its 60 f lockout. `SFX_REFUSE` plays.
   The Limitless power-up (`POWERUP_FREE_MP`) makes spells free, as Bombs
   and Oaths.
8. Spells keep their own cooldowns (`magic_tap_cd`, `magic_ward_cd`) and
   never touch `active_charge`, so a spell never locks A+B out. Casting does
   not reset the MP regen timer.

## Resource economy

- One MP pool for spells, Oath Arts (1 MP) and Spirit Convergence (full
  MP), as in FFA. Attack spells 1 MP; wards 2 MP; Cure 5 MP.
- MP regen speeds up from 1 per 192 f (3.2 s) to **1 per 144 f (2.4 s)**;
  Picsean's perk stays 1 per 96 f (1.6 s).
- Attack cooldowns: Moonfire 36 f, Thunder 45 f, Hex 30 f, Blizzard 30 f,
  Bramble 40 f. Ward lockout 60 f after the ward ends; Cure 120 f and once
  per room.
- Spell damage `S = base + (atk >> 1)`. No Will bonus (Will belongs to MAX
  arts; Carbon review). Weakness (+50 %), LCK crits, Colossus caps,
  heavy-body status resistance and kill rewards all apply because every hit
  goes through `combat_apply_player_shot_hit`.
- While a ward is live, Will does not charge (a ward is protection, not
  restraint - same reasoning as Stoneskin's shield).

## Per-hero spells (class element unchanged: fire/lightning/shadow/ice/poison)

### Wolfkin (fire 0x01): melee kit, so his magic reaches out and guards

- **Tap: MOONFIRE** (1 MP, 36 f). FFA Fire, **the game's homing spell**.
  Flies along the aim at 2 px/f; every 4 frames it picks the nearest body
  within 96 px in its forward half-plane and turns one dir8 step toward it
  (arcs, never U-turns). TTL 100 f. Direct hit S = 4 + 1 = 5 at base,
  hitstop 3, guaranteed BURN; on disappearance (hit, wall or TTL) it bursts
  for 3 to every other body within 14 px. Burns trees, opens cracked walls,
  breaks crystals (ordinary fire projectile tile rules).
- **Hold: FLAME WARD** (2 MP, up to 3.0 s). Three wisps orbit at 16 px.
  Each wisp has 2 charges: touching a hostile shot erases it (boss shells
  included, not the Reaper scythe) or touching a body sears it for 2 +
  BURN (each wisp at most once per 24 f). The ward ends when all wisps are
  spent. Answers his worst matchup: bullets from range.

### Sauran (lightning 0x04): the heavy, so his magic is a sure strike

- **Tap: THUNDER** (1 MP, 45 f). No travel: a 6-frame telegraph column on
  the best body in the aim half-plane within 104 px, then the strike on
  frame 7: S = 5 + 1 = 6, guaranteed STOP 10 beats (elites/bosses 3),
  hitstop 3, screen shake. On frame 15 it chains once to the nearest other
  body within 48 px for half damage + SLOW. No body: it strikes the floor
  40 px ahead and throws a switch or phase plate there.
- **Hold: STONESKIN + STATIC** (2 MP). The proven 120 f shot/body shield
  (`shield_timer`) plus a static pulse at cast: 2 dmg + STOP 8 to bodies
  within 28 px.

### Corvin (shadow 0x08): the trickster, so his magic is control

- **Tap: HEX** (1 MP, 30 f). A dark orb at 2 px/f, up to 64 px or the first
  body, then it bursts within 18 px: S = 3 + 1 = 4. The body it struck gets
  a guaranteed CONFUSION 16 beats (its shots wound other monsters); splash
  bodies 50 %. Heavies get MUTE instead.
- **Hold: SHADOW VEIL** (2 MP). HASTE 20 beats, 20 f i-frames, and hostile
  shots within 20 px at cast dissolve. Haste replaces a harmful status (one
  player status slot).

### Picsean (ice 0x02): the mage, so his magic is the deepest

- **Tap: BLIZZARD** (1 MP, 30 f). FFA Ice: an icicle at 3 px/f that **the
  D-pad steers** after release (one dir8 step per 4 frames toward the held
  direction). TTL 70 f, hits up to 2 bodies. S = 3 + 0 = 3, guaranteed
  STOP 12 beats ("snowman"; heavies resist per status rules). Bridges spike
  beds (ice tile rule), breaks crystals.
- **Hold: CURE** (5 MP, once per room, 120 f). FFA Cure + Heal: +2 HP (one
  heart), cleanses any harmful status, 20 f i-frames, heart chime. Refused,
  nothing spent, when it could neither heal nor cleanse.

### Vespine (poison 0x10): the glass cannon, so her magic is area + safety

- **Tap: BRAMBLE** (1 MP, 40 f). Thorns erupt along the aim: four eruptions
  at 16/30/44/58 px, 5 frames apart, each hitting bodies within 12 px; each
  body at most once per cast for S = 2 + 2 = 4, guaranteed POISON. Stops at
  the first wall; wilts trees into rubble.
- **Hold: THORN MIRROR** (2 MP, 2.0 s). Hostile shots entering 14 px turn
  back as her own poison shots (dmg 3, reversed). Boss shells are erased
  instead; the Reaper scythe is untouched.

## Whole-kit balance (base stats, Will 1, no relics)

DPS = damage per second. Tap "sustained" is MP-limited (1 cast / 2.4 s,
Picsean 1.6 s); "burst" is the cooldown cadence from a full bar.

| Hero | A (free) | B tap (1 MP) | B hold | A+B | MAX (full Will) |
|---|---|---|---|---|---|
| Wolfkin | Fang 3/24 f = 7.5 DPS, 64 px melee arc, pierce 2. Role: damage | Moonfire 5 + 3 splash + burn, homing 96 px. ~2 DPS sustained, 8 burst. Role: reach | Flame Ward 2 MP: 6 shot/sear charges over 3 s. Role: bullet defence | Oath 1 MP / Convergence full MP (8 lanes) | Moonfang Cross-Rend ~29-33, 360 f lock |
| Sauran | Tail 6/28 f = 12.9 DPS, 48 px. Role: damage | Thunder 6 + 3 chain + stun, 104 px sure hit. ~2.5 DPS sustained. Role: certainty + stun | Stoneskin 2 MP: 2 s shield + static 2 + stun 28 px. Role: tank | same | Thunderline Bastion ~18 + pylons, 360 f |
| Corvin | Feather 3/22 f = 8.2 DPS, long, pierce 2. Role: damage | Hex 4 in 18 px + confusion. Role: control | Shadow Veil 2 MP: haste 20 beats + i-frames + shot clear. Role: escape | same | Murderstorm Eclipse 16/21, 360 f |
| Picsean | Bubble 3/30 f = 6 DPS, room range. Role: damage | Blizzard 3 x2 bodies + freeze, steerable. Role: control + puzzles | Cure 5 MP once/room: +1 heart, cleanse. Role: sustain | same | Tide Vortex room sweep, 360 f |
| Vespine | Stinger 6/20 f = 18 DPS, 48 px. Role: damage | Bramble 4 x up to 4 bodies + poison along a line. Role: area | Thorn Mirror 2 MP: 2 s reflect. Role: punish shooters | same | Royal Stinger ~20 + poison, 360 f |

Roles: **A** is sustained damage and costs nothing. **Tap** is the elemental
tool: reach (Wolfkin), certainty (Sauran), control (Corvin, Picsean), area
(Vespine), plus room puzzles; MP gates it so it never replaces A. **Hold** is
survival, one distinct verb per hero (barrier, shield, haste, heal,
reflect). **A+B** is the stage-earned Oath at 1 MP and Spirit Convergence
at full MP; spells now make "full MP" a real choice. **MAX** stays the
restraint payoff (Will from not attacking, 360 f recast lock), several
times a spell. No spell beats A's sustained DPS; spells win through reach,
area, status, defence or room effects. MAX numbers come from main after the
Max-Will v2 merge (#137).

**A+B (kept, strengthened):** before this change A+B below full MP was a
dull refusal until the first Colossus unlocked an Oath. Because spells keep
MP below full more often, **Shard Wake (the first Oath) is now known from
the start of the run**; each Colossus victory unlocks the next art. Full-MP
A+B (Spirit Convergence) is unchanged.

## Carbon review (gemini-review -m carbon, $0.107)

Verdict: ship with changes. Adopted: hold threshold 24 f; Cure 5 MP once
per room; Thunder base 5 + telegraph + STOP 10 + SLOW chain + 45 f;
Blizzard 2 hits, STOP 12, 4 f turns; Hex 18 px, guaranteed confusion only
on the struck body; Veil haste 20 / 20 f i-frames; Bramble base 2, 40 f;
Moonfire 36 f; Flame Ward wisps spend 2 charges each; wards cannot be
recast while live (+60 f); spells do not touch `active_charge` (no A+B
lockout); Will paused while a ward is up; no MP-regen reset on cast; no
Will bonus on spell damage; hitstop on Thunder and Moonfire; no persistent
entity slots for ward logic; Shard Wake from run start.

## Implementation

- New `src/game/magic.c` (`#pragma bank 31`, the empty bank) + `magic.h`
  + `magic_art.inc` (generated by `scripts/gen_magic_art.py`). room.c's B
  press block becomes one call, `magic_input(keys, pressed, damage)`, which
  also ticks live spells; `secondary_fire` stays for the item path.
- Moving spells (Moonfire, Hex orb, Blizzard) are player projectiles tagged
  `ai_data[7] = 0xA0 | spell` (`MAGIC_IS_SHOT`; all `ai_data[3]` flag bits
  are taken). They keep wall/tree/crack/crystal/switch rules; the shimmer
  sprite swap skips them. `combat_apply_player_shot_hit` calls
  `magic_on_hit(shot, j, killed)` for them on both the survive and kill
  paths. Bursts trigger when a tracked shot disappears.
- Area effects (bursts, Thunder, static, Bramble, Flame Ward, Thorn Mirror
  reflect) use a transient inert `PROJ_AUX_VORTEX` carrier and per-cast hit
  masks (the Max-Will v2 pattern); damage still flows through
  `combat_apply_player_shot_hit`.
- Art: 16 hand-pixelled 8x8 tiles (no GPT Image spend) in VRAM bank-1 OBJ
  160..175, reloaded by `room_load_dynamic_fx_identity` on every room entry
  and Pack/map return. Palettes: fire 4 (heart red), lightning 5 (coin
  amber), shadow/ice 1 (the hero's own violet/cyan), poison 7 (orc green).
- Sound: per-spell CH1/CH4 voices through `sfx_claim_channels`, respecting
  `sfx_melody_locked`.
- Room-bound state (tracked shots, pending strikes, Cure flag) drops when
  `entity_init_room` bumps `magic_room_serial`; wards cross doorways. New
  heroes call `magic_reset` from `player_apply_class`.
- Copy: help page "B TAP SPELL 1 MP" / "B HOLD WARD 2+ MP"; Pack tips,
  class-select tips and item names (Moonfire, Thunder, Hex, Blizzard,
  Bramble) updated.

## Tests (`scripts/test_magic.py`, headless PyBoy)

Per hero: tap casts the attack spell and spends 1 MP; hold casts the ward
and spends its cost; B-then-A and A-then-B both run the A+B chord and cast
no spell; too little MP refuses without spending. Spell checks: Moonfire
turns toward an off-axis body and hits it; Blizzard follows a held D-pad;
Thunder stuns and chains; Hex confuses; Bramble poisons each body once;
Flame Ward erases a hostile shot; Stoneskin raises the shield; Veil hastes;
Cure heals once per room; Thorn Mirror reflects a shot. `test_new_game_start.py`
and `test_watch_intro.py` keep passing; `test_signature_balance.py` is
replaced.
