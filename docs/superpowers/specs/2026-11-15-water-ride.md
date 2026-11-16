# Water ride: Tide Raft and Picsean swim

Date: 2026-11-15. Playtest note: "I'm walking on water, which is cool, but it
should show you on a raft or something."

## Why the champion could cross water

Not a bug. `WAYGEAR_TILE_PASSABLE` (`src/game/waygear.h`) makes
`BGT_WILD_WATER` (ponds and streams) and `BGT_GATE_WATER` (Riftwild water
gates) walkable when the champion is a **Picsean** (`class_id == 3`, innate
"you can swim there") or owns the **Tide Raft** waygear (`WAYGEAR_RAFT`, the
second Riftwild Warden's reward). No Oath touches water, and other classes
without the raft stay blocked. The ability worked; the art just
showed the normal walk cycle on top of the water.

## What is drawn now

While the tile under the feet (`x + 8, y + 12`, the same feet probe the
collision box uses) is water:

| Who | Visual | OAM | OBJ tiles |
|---|---|---|---|
| Non-Picsean with the Tide Raft | 24x8 log raft under the feet, two-frame foam wake (8-frame beat), 1 px bob (16-frame beat) | 36..38 (OAM 39 stays free for the reward icon) | VRAM bank 1, 0..5 |
| Picsean | swim pose: torso sinks 5-6 px and bobs, a 16x8 ripple ring replaces the legs, so the water shows through where they were. Ring widens and throws foam on the second beat | none extra (reuses champion OAM 2..3) | VRAM bank 1, 6..9 |

**Why the Picsean swims instead of rafting:** the Picsean is the river
folk. Swimming is the class's innate traversal and the dialogue already says
"YOU CAN SWIM THERE", so a raft would misdescribe the ability. A Picsean
with the Tide Raft still swims, because the innate comes first. The swim also costs
no OAM.

The raft uses OBJ palette 5 (coin gold/brown/cream), which every combat room
loads. The ring uses the champion's own palette, so tier upgrades and status
pulses still apply. Visual only: collision, speed, WRAM layout (one new byte,
`water_ride_mode`) and save data are unchanged.

## Art

GPT Image 2.6 Sunburst (`gpt-image-2.6-sunburst`) raft and swim candidates,
generated from a headless screenshot of the hero on a Riftwild pond, were
hand-quantized into `grids.rs` (`WATER_RAFT_A/B`, `WATER_SWIM_A/B`).
`quintra-assets` emits `src/render/water_ride_gen.c`. Spend: 2 calls, about
$0.20.

## Budget

- OBJ VRAM: bank-1 OBJ 0..39 was unused (the stage-boss poses start at 40,
  Hexa limbs at 88, the boss poses at 128, the vertical shots at 208 and
  the status marks at 224). The 10 tiles are re-uploaded whenever the
  champion steps onto water (160 B, once per stretch of water).
- OAM: the raft takes entity OAM 36..38 only while it is shown. Compact rooms
  now draw entities before the champion, as scrolling rooms already did, so
  the raft keeps those slots in crowded rooms. Entities rotate through the
  remaining 33 slots.
- ROM: `[layout] OK`. The new code and atlas are pinned to bank 17. The
  call from `place_player_sprite` costs bank 1 eight bytes (266 → 258 free).
  An autobanked atlas had landed in bank 1 below the 256-byte floor.
- The raft is hidden during Riftwild seam slides (`room_stream_wide_seam`).

## Verification

- `scripts/test_water_ride.py` (CI step "PyBoy water ride"): Wolfkin with the
  Tide Raft gets no raft on land. On a pond it gets OAM 36..38 with palette 5,
  bank 1, centred under the feet, both wake frames and both bob offsets, and
  the legs are unchanged. Back on land, the raft OAM is parked. A Picsean
  without the raft swims (ring tiles in OAM 2..3, torso sunk 5-6 px, never the
  raft), and the legs return on land.
- cargo `water_ride_frames_are_distinct_and_match_source` golden-checks the
  atlas.
- Before/after GIFs: `docs/previews/water-ride/`, same seed and path,
  headless PyBoy.
