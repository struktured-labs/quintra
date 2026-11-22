# Automated balance measurement (human-skill bots, per-stage report, CI gate, telemetry)

Status: implemented (this PR). Requested by Carmelo via Quintra CPO: he has not
got past stage 3, the stage 3 Colossus ends his runs, and status effects that
land at bad moments are the other suspected run-killer. Pricing needs an
estimated human first-clear time and a difficulty curve.

## Goals
1. Bots at three human-like tiers (non-expert, average, skilled) plus the
   unhindered pilot (`bot`, the pilot's ceiling).
2. Per-stage logs: time, deaths, damage taken vs dealt, burst damage, HP /
   MP / coins / stats / items, hero, Colossus time-to-kill, status landings.
3. A report: stages 1-9, median and p25/p75 per tier, spikes, a stage 3
   Colossus panel, a status-at-bad-moments panel, and an estimated first
   clear (death wipes the run, `sram_clear_run`) with the share of it inside
   Steam's 2-hour refund window.
4. CI gates with small samples; the full sweep is a separate script.
5. Opt-in local telemetry from Carmelo's own sessions, to calibrate the bots.

## Human model (same numbers in Lua and Python)
The pilot decides each frame; a filter degrades it like hands do. Only the
pressed buttons change. Nothing writes cartridge RAM.

| tier | reaction to a new shot | shots never noticed | lapse (stale input) | D-pad slip per direction change | aim off by 45° per attack | dropped attack per press | puzzle think | room-entry pause |
|---|---|---|---|---|---|---|---|---|
| skilled | 15 f (250 ms) | 10% | 0.15%/f, 6-12 f | 4%, 2-5 f | 6% | 3%, 3-6 f | 3-10 s | 0.1-0.3 s |
| average | 21 f (350 ms) | 25% | 0.35%/f, 10-20 f | 10%, 3-8 f | 14% | 8%, 4-10 f | 10-30 s | 0.3-0.75 s |
| non-expert | 27 f (450 ms) | 40% | 0.6%/f, 15-30 f | 20%, 4-12 f | 22% | 15%, 6-14 f | 20-75 s | 0.5-1.5 s |

Reaction delay is modelled per projectile: a shot is invisible to the pilot
until it has been on screen for the reaction time, and a missed shot stays
invisible. While Blind is on, only shots within 32 px are seen (the pilot
reads RAM, so darkness would otherwise cost it nothing). Slips and dropped
attacks fire on input edges, as hands err when they change, not mid-hold.
RNG is private and seeded per (tier, seed, hero), so a ROM + seed
is reproducible. `scripts/test_balance_harness.py` keeps both copies equal.

## Two harnesses
- **PyBoy slices** (`scripts/balance_arena.py`): progression-matched
  `make_stage_states.py` checkpoints, played by the maintained PyBoy pilot
  (`run_pyboy_checkpoints.controller_action`) through the filter. `boss` =
  live Colossus arena until kill/death/180 s; `entry` = the stage's first
  combat room at full HP until cleared/death/60 s. The 1080-slice Normal sweep
  (4 tiers x 5 heroes x 9 stages x boss+room x 3 seeds) takes 13 min on 20 cores.
  This is the authoritative source for the curve and the gates.
- **mGBA whole runs** (`scripts/balance_sweep.py` + `quintra_human_model.lua`
  loaded by `quintra_balance_bot.lua`): cold boot to death/win, or a stage
  slice through the title's Rift Index warp (pure input, the cartridge's own
  stage-ready build). Writes one row per stage reached. Adds a CPU watchdog
  (`hang` rows with a Lua traceback) and a 3-minute no-progress stop
  (`stalled`, excluded from difficulty and reported as harness health).

The mGBA pilot has not been maintained since 2026-08-31 and the Endurance
workflow has failed weekly since at least 2026-10-12. This PR fixes its boot
(power-on intro, foyer vignette) and a per-frame full-field search that made
40k-frame trials time out, but it still loses its way in stage 1. Until that
is fixed (issue filed), whole-run numbers are harness-health only.

## Metrics
Per slice / stage row: outcome, frames, damage taken / dealt / hits, HP start
/ end / min / max, burst = damage inside a trailing 2 s window (max, and spikes
>= 40% of max HP), status landings (new kind or a refresh that raises the
timer), harmful ones (poison..curse; regen/haste/inversion excluded), during
a live Colossus, at <= 1/3 HP, and for deaths the last harmful status and its
age, plus exposure = frames under a harmful status or within 5 s of one.
The report shows deaths after a status within 3 / 5 / 10 s by effect and
stage, and the lift: (share of deaths within 5 s of a status) / (share of
play time exposed). Lift near 1 means statuses are incidental; well above 1
means they kill.

## First-clear model (estimate)
Per stage and tier: P(pass) = P(survive a room)^rooms x P(beat Colossus),
each simulated player drawing its odds from the Beta posterior of the
measured counts (Jeffreys prior), so thin samples widen the range. Room
timeouts (pilot lost) are excluded, not counted as survival;
rooms = mean seeded entry-to-Colossus maze distance (cartridge topology
mirror) x 1.6 detour, 75% of them with combat. Stage time = rooms x measured
room time + 12 s transit per room + 1.5 puzzles x think time + Riftwild leg
(1.5-4 min by tier) + Colossus time. A Monte Carlo player restarts at stage 1
on death (+45 s); a boss death costs the stage's pre-boss time plus the
measured attempt length. Two variants: no learning (bots do not learn), and
learning (each visit to a stage moves its odds 10% toward the next tier up).
Slices start at the checkpoint's HP, so attrition between rooms is not
modelled: the hours are a lower bound. All model constants live at the top of
`scripts/balance_report.py`; telemetry should replace them.

## CI
`rom` job step "Balance smoke" (placed before the known-red steps, see #194):
stage 3 checkpoints for all five heroes, average tier, three seeds of the
Colossus fight (15 fights, about two minutes), then `balance_report.py
--check scripts/balance_thresholds.json`. Gates: stage 3 Colossus win rate
(average tier), mean share of the Colossus's HP removed (a continuous metric
with far more power than 15 coin flips), and the share of deaths within 5 s
of a harmful status (only once there are enough deaths). Thresholds sit
just past today's values, so a change that makes any of them worse fails
CI; the design targets in the JSON are for the tuning work, not gates.
Slices are deterministic for a ROM, so a red gate is a real change in
behaviour, though any ROM change re-rolls the fights.

## Telemetry (opt-in, local only)
Open the web build with `?telemetry=1` (remembered in that browser;
`?telemetry=0` stops, `?telemetry=clear` also wipes). The player samples WRAM
ten times a second and keeps per-run, per-stage stats in localStorage: game
play seconds (the cartridge's own run timer), wall time, damage, hits,
Colossus time, burst, status landings (in boss / at low HP), and for a death
the last status and its age. An "Export stats" button appears and downloads
JSON + CSV. Nothing is sent anywhere. Addresses are baked into the page from
the linker map at build time. No cartridge change; the Pocket/MiSTer builds
are untouched. Off by default, so the default page is unchanged.

## Baseline (2026-11-22)
See `docs/balance/2026-11-22-baseline-{normal,easy}.md`. The pilot itself
loses almost every Normal Colossus fight (the repo's own boss curriculum
audit: 0/15 on stages 1-3), so Normal win rates are floors; the relative
signals and the Easy sweep carry the curve. The stage 3 Colossus is flagged
on Normal for every tier (6-9% of its HP removed vs 18-34% at stages 2/4).

## Not done
- A pilot that can win Normal Colossus fights (issue), which the absolute
  numbers need.
- Repairing the mGBA whole-run pilot's stage-1 routing (issue).
- `make_mgba_states.lua` entry: boot fixed here; Riftwild gate entry still
  fails after the seeded-entry change (issue).
- An SRAM stats block for Pocket sessions (would cost cartridge RAM/CPU).
