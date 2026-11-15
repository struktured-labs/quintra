# GPT Image 2.6 art pass 3: animated mini-bosses

Redraw the four remaining mini-boss variants (Orc, Skeleton, Bomber, Warlock) from Sunburst edits of their shipped art, and animate all five variants, including the pass-1 Sentinel. Each candidate was a three-panel edit (idle, opposite-foot walk beat, attack telegraph) of the upscaled existing sprite, hand-quantized back to 16×16 with the same three colours plus transparency.

Runtime: the five variants still share the four-tile SPR_BOSS slot. `miniboss_anim_tick` picks pose 0/1 on a 16-frame beat, or pose 2 for the last 12 ticks of the volley countdown (the existing white blink stays at 8). It streams the 64-byte pose into SPR_BOSS only when the pose changes. The resident pose is cached in the mini-boss `vx` byte, which mini-boss bodies never use, so there is no new WRAM and suspend layout is unchanged. Unchanged: OAM count (4), palettes and glyph roles (Sentinel body stays colour 1 for Bloodmoon), hitbox 0xEE, movement, volley patterns, cadence, HP and damage. Bruisers keep their own art; they come in the monster pass.

Data: one contiguous 960-byte atlas (variant × 3 + pose) plus its loader in an autobanked generated unit. The old 2×-scaled `sprite_miniboss_orc`/`_skeleton` arrays are removed from bank 2.

Acceptance: quintra-assets golden and frame-contract tests, full ROM build and layout gate, PyBoy suspend/cold-resume and mini-boss checks, plus headless before/after stills and GIFs per variant.
