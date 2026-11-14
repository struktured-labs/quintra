# GPT Image 2.6 native art pass 2: Hexa Dragmar

Refine the shipped Hexa Dragmar final-boss art — the 16 carapace background tiles, the five class limb heads (idle and telegraph/active poses), and the flip-composed core tiles — using existing upscaled sprites as Sunburst edit inputs. Compare downsampled candidates at native resolution. Preserve the 16-tile atlas, the tilemap and flip attributes, exact palette indices, 16×16 limb silhouettes and two poses, and the 2×2 flip-composed socket and core tiles (SL, CC, CO, CP).

This is a refinement of the current shipped fight, not the rev-4.x redesign (PR #57), which still awaits owner decisions and is out of scope.

No runtime changes: tile indices 40..55, map, attributes, banks, OAM count (five limbs × four sprites), the per-scanline limb budget (≤6), collision and hitboxes, animation frame counts and timing, and the spotlight palette swap remain unchanged. Shared boss shot glyphs in `boss_projectile_art.c` are not Hexa-specific and stay unchanged. Quantize reference edits to the existing palettes (background palette 5, four colours, for body and core; object palette 5, three opaque colours plus transparency, for limbs). Reject muddied or identity-changing candidates; manual pixel cleanup is expected at native size.

Acceptance: complete ROM build and ROM layout gate; `scripts/test_hexa_dragmar.py` (including victory and meta contracts) and `scripts/test_hexa_body_art_and_contrast.py`; dense-phase stall and scanline counts no worse than main; smoke. Provide nearest-neighbour before/after fight screenshots (opening, limbs firing, spotlight, quarter HP), a raw-candidates sheet, and a combined comparison. No merge or hardware deployment.
