# GPT Image 2.6 native art pass 1

Refine Wolfkin, Sauran, Corvin, Picsean, Vespine and Crystal Caverns Sentinel using existing upscaled sprites as Sunburst edit inputs. Compare downsampled candidates at native resolution; preserve recognizable species, exact palette indices, foot anchors, and silhouettes. Sentinel includes the stage-zero 32x32 crowned crystal Colossus and compact 16x16 miniboss representation.

No runtime changes: fixed arrays and tile ranges, banks, OAM count, collision, animation frame counts and timing remain unchanged. Heroes retain idle, two authored walk beats, hurt and claim; ascended art stays unchanged this step. Colossus retains idle/refraction. Quantize reference edits to existing three opaque colors plus transparency. Reject muddied/identity-changing candidates; manual pixel cleanup is expected at native size. Keep source grids authoritative and regenerate C.

Acceptance: generator golden tests, complete build and ROM layout gate, relevant headless PyBoy animation/boss checkpoints. Provide native/nearest-neighbor before/after sheets and raw model candidates. No merge or hardware deployment.

Note: the Warden mini-boss loads OBJ slot 6, the stage boss palette. Crystal Caverns and Bloodmoon both use this mini-boss. Colour 2 is cyan in Crystal Caverns but near-black in Bloodmoon, so the body stays colour 1 and only the rim and visor use colour 2.
