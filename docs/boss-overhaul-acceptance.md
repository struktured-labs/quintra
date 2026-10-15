# Boss overhaul implementation acceptance

Current ROM: `da33fb7b5b23b0ba5b4e110edd7270dae630967a7368e1f80bb0e05b7fa9b69a`.

The requested boss feature pass is implemented and emulator-verified. This is
not certification of final difficulty balance, subjective sound quality, or
Pocket/MiSTer/browser-emulator compatibility. No hardware or public deployment,
commit, push or external message was performed for this acceptance.

## Requirement audit

| Requested outcome | Current implementation and observed evidence |
| --- | --- |
| Quieter floors and more readable bosses | Arena-specific low-contrast floor atlas/palette; moving boss silhouettes no longer depend on detached terrain murals. Native focus/atlas/menu tests cover six ordinary bosses, Reaper poses, Cinder forms and Serpent body. Current native frames were inspected. |
| Different projectile colors and sizes | Five native silhouettes: pellet, orb, seed, bolt and crescent; distinct palettes and collision footprints. Native atlas/OAM and menu-restoration tests pass; native size-comparison screenshot inspected. |
| Nonlinear, predictable projectile patterns | Arcs, waves, spirals and returning crescents, plus speed bands and lanes. Native trajectory and eight-boss three-phase volley tests pass; Cinder has its own pattern checks. |
| Projectiles producing different child patterns | Three bounded two-generation families: seed → wave → arc; spiral → returning crescent → bolt; bolt → perpendicular arc forks → wave. Native ancestry, warning, direction and lifetime tests pass. Shared hostile sprite budget includes summoned enemies' shots. |
| More movement and multiple phases | All nine bosses have health thresholds and transition windows; six moving-body focus checks, separate Serpent cycles, Cinder pack/Rex/reprise and Reaper link cycles verify their distinct mechanics. |
| AOE attacks and minion summons | Locked-position blast warnings, Mire's safe-center ring, and bounded Spider/Mire/Void escorts. All 24 general warning/escape/allocation cases, eight Mire cases and eight summon cases pass. Failed warning allocation cancels damage. |
| Trick boss with an obvious alternating tell | Reaper warning/linked/exposed poses, tether, palette, HUD words and voice cue. Native tests prove fresh-shot reflection, airborne-shot grace, damage sharing and lethal outcomes. A continuous controller respects the tell and survives three links; deliberately ignoring it fails the same survival gate. |
| Larger, longer Serpent that partitions the arena | 28 retained segments, broad 16-pixel body, final growth sweep and full-length unwind. Native coverage rises from 43 to 56 cells at maximum growth; collision, no-shrink, two-cycle and OAM checks pass. A fresh controller-only combat route defeats it. Later self-overlap remains possible. |
| Distinct boss noises, also audible near doors | Nine pulse/noise profiles and arrival/attack/phase/pain/death calls; reduced-volume approach calls at the corresponding sealed door. All nine door captures and four shared movement-call captures have expected profiles and non-silent native PCM. Instrumented and uninstrumented WAVs match byte-for-byte. No claim of subjective listening approval. |
| Animated webpage, with separate phase cards | Served page has 61 cards: 27 health phases, 18 transitions and 16 explicit mechanic cycles. Native timing/aspect, fixture disclosure, enlarge, selected-only audio, shortlist and modal cleanup pass browser acceptance. |

## Bound evidence

- Full fresh native acceptance: [30 checks, all passing](../builds/boss-acceptance-da33fb7b-1790466667225806468/report.json), 40.38 seconds. Individual source hashes, arguments, durations and unabridged logs accompany the report.
- Current [capture and full event traces](../builds/boss-phases-da33fb7b-97b05c62/capture.json) and [browser verification](../builds/boss-phases-da33fb7b-97b05c62/browser-check.json).
- Live [animated review](http://100.120.23.124:8919/).
- [Reaper controller respects link](../builds/reaper-controller-da33fb7b-66edaf0d/respect/capture.json): boss 127 → 37 HP, player 15 → 13 HP over three completed links. [Reckless control](../builds/reaper-controller-da33fb7b-66edaf0d/ignore/capture.json): dies during the third link. Both use staged half-health entry and world-state-aware steering, not human vision.
- [Current Serpent controller combat](../builds/serpent-escape-da33fb7b-41f663cb/3-reactive-dash-signature-combat/capture.json): victory in 6399 LCD frames, 12 HP remaining, no runtime RAM writes after staged entry. The webpage's separate archived controller video is explicitly older footage.
- Historical negative controls, rejected experiments, raw-art inspections and implementation details: [working log](boss-overhaul.md).

## Performance and handoff limits

Fresh dense-boss probes deliver 703–964 game updates per 1200 display frames,
with no more than 12 hostile sprite units and observed stalls of two or three
display frames. This is bounded load, not a claim of locked display-rate game
logic. Serpent retains 715/1200 versus the original smaller body's 745/1200,
inside the existing 95% guard. Ordinary-room regression results are
176/175/137 updates per 180 display frames.

The implementation pass is ready for the user's requested boss-by-boss review.
Further art preferences, listening feedback and human difficulty tuning remain
normal refinement work; they are not silently represented as automated passes.
Changes remain in the shared worktree. Unrelated user files were preserved.
