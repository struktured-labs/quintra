<!-- Baseline for scripts/balance_thresholds.json. ROM 68755c1d (main 62b83e51), Easy; `scripts/balance_arena.py --stages 1-9 --difficulty easy --seeds 2 --skills bot average nonexpert` plus a bounded mGBA whole-run sample (`balance_sweep.py --mode full --seeds 1 --frames 108000`). -->

> **Read first:** the controller pilot under these tiers cannot yet win Normal Colossus fights that people win (the repo's own `audit_boss_curriculum.py` also scores 0/15 on stages 1-3), so measured win rates and the measured first-clear table are floors. Use the relative signals (boss HP removed, fight length, burst, status timing, spikes) and the scenario table.

# Quintra difficulty report

540 human-model slices; tiers nonexpert, average, bot; stages 1-9. Times in seconds unless noted; `median (p25-p75)`. Model numbers are **estimates**.

## Stage 3 Colossus (flagged by playtest)

| tier | fights | win rate | deaths | time-to-kill s (wins) | attempt s | dmg taken | max 2 s burst (% max HP) | burst spikes/fight | boss HP left when lost | mean boss HP removed |
|---|---|---|---|---|---|---|---|---|---|---|
| nonexpert | 10 | 0% | 10 | n/a | 79.9 (76.5-82.3) | 16 (16-17) | 6 (6-6) | 0.0 (0.0-0.0) | 51 (41-60)% | 50% |
| average | 10 | 10% | 9 | 70.7 (70.7-70.7) | 75.7 (71.5-90.7) | 16 (16-17) | 6 (6-6) | 0.0 (0.0-0.0) | 33 (23-42)% | 69% |
| bot | 10 | 60% | 4 | 51.7 (48.7-60.3) | 64.6 (50.4-78.4) | 14 (11-16) | 6 (6-6) | 0.0 (0.0-0.0) | 29 (21-36)% | 89% |

## Status effects at bad moments

| tier | harmful landings | per boss-minute | in boss fights | at low HP (≤1/3) | deaths | deaths after status ≤3 s | ≤5 s | ≤10 s | play time within 5 s of a status | lift (≤5 s share / exposure) |
|---|---|---|---|---|---|---|---|---|---|---|
| nonexpert | 10 | 0.00 | 0 | 1 | 44 | 0/44 (0%) | 0/44 (0%) | 0/44 (0%) | 1% | 0.00x |
| average | 16 | 0.00 | 0 | 1 | 34 | 0/34 (0%) | 0/34 (0%) | 0/34 (0%) | 1% | 0.00x |
| bot | 10 | 0.00 | 0 | 0 | 23 | 0/23 (0%) | 0/23 (0%) | 0/23 (0%) | 1% | 0.00x |

Lift compares the share of deaths that follow a status with the share of play time spent under or just after one: about 1x means statuses are along for the ride; well above 1x means they cause deaths.

All status landings by type: blind 26, haste 25, bleed 5, mute 3, stop 2

## Difficulty curve by stage

Boss: Colossus fight from its live arena checkpoint. Room: the stage's first combat room at full HP.

### nonexpert

| stage | boss win | boss TTK s | boss attempt s | boss dmg | room death | room clear s | room dmg/min | dealt:taken | est. stage min | est. P(pass stage) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 8/10 | 67.4 (50.6-78.8) | 72.4 (55.2-99.4) | 12 (8-16) | 0/0 | n/a | n/a | n/a | 16.4 | 55% |
| 2 | 0/10 | n/a | 48.5 (43.9-54.9) | 16 (16-16) | 1/2 | 47.8 (44.4-51.3) | 14.7 (9.5-19.8) | 14.8 (7.4-22.1) | 18.2 | 0% |
| 3 | 0/10 | n/a | 79.9 (76.5-82.3) | 16 (16-17) | 1/2 | 34.1 (33.0-35.3) | 21.5 (18.3-24.8) | 21.7 (15.0-28.4) | 16.1 | 0% |
| 4 | 10/10 | 62.2 (48.0-73.9) | 62.2 (48.0-73.9) | 8 (6-10) | 0/0 | n/a | n/a | n/a | 18.5 | 64% |
| 5 | 9/10 | 54.0 (46.4-68.6) | 56.3 (47.6-73.4) | 10 (6-11) | 0/3 | 51.8 (39.7-52.6) | 1.2 (1.1-1.7) | 217.0 (217.0-219.5) | 22.2 | 13% |
| 6 | 2/10 | 45.1 (40.6-49.6) | 56.3 (54.3-57.6) | 17 (17-17) | 0/0 | n/a | n/a | n/a | 21.0 | 14% |
| 7 | 10/10 | 48.8 (33.8-59.7) | 48.8 (33.8-59.7) | 12 (8-13) | 3/3 | 51.6 (49.8-54.8) | 21.0 (19.8-22.3) | 4.1 (2.4-4.6) | 22.5 | 0% |
| 8 | 9/10 | 41.1 (30.4-44.3) | 41.1 (31.0-51.9) | 6 (4-10) | 0/0 | n/a | n/a | n/a | 20.8 | 53% |
| 9 | 1/10 | 116.1 (116.1-116.1) | 132.7 (117.7-142.8) | 18 (18-20) | 0/3 | 21.7 (15.4-34.2) | 0.0 (0.0-0.0) | 0.0 (0.0-6.5) | 19.8 | 1% |

### average

| stage | boss win | boss TTK s | boss attempt s | boss dmg | room death | room clear s | room dmg/min | dealt:taken | est. stage min | est. P(pass stage) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 8/10 | 61.9 (37.5-76.4) | 70.1 (42.5-92.6) | 9 (6-11) | 0/0 | n/a | n/a | n/a | 14.6 | 55% |
| 2 | 4/10 | 54.9 (43.2-64.4) | 46.8 (41.9-61.6) | 16 (15-16) | 0/0 | n/a | n/a | n/a | 15.1 | 29% |
| 3 | 1/10 | 70.7 (70.7-70.7) | 75.7 (71.5-90.7) | 16 (16-17) | 2/2 | 51.7 (49.1-54.2) | 18.8 (17.9-19.7) | 6.4 (5.4-7.3) | 17.6 | 0% |
| 4 | 10/10 | 58.7 (29.6-76.2) | 58.7 (29.6-76.2) | 6 (4-9) | 0/1 | 20.6 (20.6-20.6) | 0.0 (0.0-0.0) | 99.0 (99.0-99.0) | 12.5 | 2% |
| 5 | 10/10 | 47.7 (28.3-65.9) | 47.7 (28.3-65.9) | 8 (4-10) | 0/2 | 39.2 (38.8-39.6) | 6.1 (4.6-7.5) | 63.4 (45.6-81.2) | 17.4 | 7% |
| 6 | 3/10 | 35.7 (28.9-37.8) | 48.3 (41.4-50.6) | 17 (12-17) | 0/0 | n/a | n/a | n/a | 19.1 | 19% |
| 7 | 10/10 | 29.0 (19.8-37.8) | 29.0 (19.8-37.8) | 7 (5-9) | 3/3 | 49.8 (49.5-51.3) | 22.0 (21.8-22.4) | 1.7 (1.4-2.1) | 20.0 | 0% |
| 8 | 10/10 | 34.1 (20.0-40.2) | 34.1 (20.0-40.2) | 5 (4-7) | 0/0 | n/a | n/a | n/a | 19.0 | 58% |
| 9 | 5/10 | 104.6 (91.8-118.7) | 106.6 (97.3-123.2) | 18 (16-19) | 0/7 | 14.5 (12.2-24.2) | 0.0 (0.0-0.0) | 0.0 (0.0-3.0) | 15.6 | 14% |

### bot

| stage | boss win | boss TTK s | boss attempt s | boss dmg | room death | room clear s | room dmg/min | dealt:taken | est. stage min | est. P(pass stage) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 9/10 | 82.4 (74.8-87.0) | 84.1 (75.3-89.1) | 8 (5-10) | 0/0 | n/a | n/a | n/a | 13.0 | 62% |
| 2 | 2/10 | 46.1 (38.7-53.4) | 55.6 (41.3-67.1) | 16 (16-16) | 2/3 | 38.5 (32.0-39.6) | 25.0 (14.8-25.8) | 1.8 (1.8-25.6) | 12.7 | 0% |
| 3 | 6/10 | 51.7 (48.7-60.3) | 64.6 (50.4-78.4) | 14 (11-16) | 0/0 | n/a | n/a | n/a | 13.0 | 42% |
| 4 | 10/10 | 59.3 (36.0-68.1) | 59.3 (36.0-68.1) | 8 (6-9) | 0/1 | 36.3 (36.3-36.3) | 0.0 (0.0-0.0) | 133.0 (133.0-133.0) | 13.9 | 2% |
| 5 | 7/10 | 39.6 (29.7-69.1) | 69.1 (35.0-176.8) | 5 (3-12) | 0/0 | n/a | n/a | n/a | 15.5 | 44% |
| 6 | 7/10 | 26.4 (24.5-39.4) | 39.4 (25.2-45.9) | 11 (7-16) | 0/0 | n/a | n/a | n/a | 17.0 | 42% |
| 7 | 10/10 | 23.0 (17.9-26.1) | 23.0 (17.9-26.1) | 6 (5-6) | 2/3 | 45.3 (43.7-47.1) | 22.1 (15.3-23.6) | 3.7 (2.4-24.9) | 16.8 | 0% |
| 8 | 10/10 | 32.1 (20.5-35.3) | 32.1 (20.5-35.3) | 5 (4-6) | 0/0 | n/a | n/a | n/a | 16.9 | 58% |
| 9 | 7/10 | 63.7 (55.1-90.2) | 90.2 (61.8-111.7) | 16 (9-18) | 0/6 | 12.7 (10.7-22.1) | 0.0 (0.0-0.0) | 0.0 (0.0-4.5) | 12.2 | 15% |

## Spikes (> 2x neighbour mean)

- nonexpert: stage 6 boss loss rate 0.80 vs neighbours 0.05
- nonexpert: stage 9 boss loss rate 0.90 vs neighbours 0.10
- nonexpert: stage 9 boss time-to-kill 116.14 vs neighbours 41.09
- average: stage 3 boss loss rate 0.90 vs neighbours 0.30
- average: stage 6 boss loss rate 0.70 vs neighbours 0.00
- average: stage 9 boss loss rate 0.50 vs neighbours 0.00
- average: stage 3 room death rate 1.00 vs neighbours 0.00
- average: stage 9 boss time-to-kill 104.56 vs neighbours 34.10
- bot: stage 2 boss loss rate 0.80 vs neighbours 0.25
- bot: stage 9 boss loss rate 0.30 vs neighbours 0.00

## Estimated human first clear (death wipes the run)

| tier | P(clear one run) | clean-run length min | runs to first clear | first-clear hours, no learning | with learning | players clearing within 2 h | 2 h as share of median first-clear time | furthest stage by 2 h |
|---|---|---|---|---|---|---|---|---|
| nonexpert | 0.00% | 175 | 389/422/467 | >200/>200/>200 | >200/>200/>200 | 0% | 0% | 2/2/2 |
| average | 0.00% | 151 | 351/397/454 | >200/>200/>200 | >200/>200/>200 | 0% | 0% | 2/3/3 |
| bot | 0.00% | 131 | 686/748/855 | >200/>200/>200 | >200/>200/>200 | 0% | 0% | 2/2/2 |

Hours are p25/median/p75 over simulated players; each player draws its own odds from the measured win/death counts, so thin samples widen the range. *Learning* moves each stage's pass odds 10% of the way toward the next tier per visit to that stage. Slices start rooms and the Colossus at the checkpoint's HP, so attrition between rooms is not modelled: treat the hours as a lower bound. Stage time = combat rooms x measured room time + transit 12s/room + puzzles + Riftwild leg + boss; path rooms come from the cartridge topology x 1.6 detour factor.

## First clear under assumed human pass odds (scenario, not measured)

Stage lengths are measured per tier above; pass odds are assumptions because the pilot cannot yet win Normal Colossus fights a person wins.

| tier times | scenario | P(pass stage) / stage 3 | P(clear one run) | first-clear hours p25/median/p75 | players clearing within 2 h | 2 h as share of median first clear | furthest stage by 2 h p25/median/p75 |
|---|---|---|---|---|---|---|---|
| nonexpert | strong | 90% / 70% | 30.1% | 2.9/4.2/6.4 | 0% | 47% | 5/6/7 |
| nonexpert | middle | 80% / 45% | 7.5% | 5.5/9.5/16.9 | 0% | 21% | 3/4/5 |
| nonexpert | struggling | 70% / 25% | 1.4% | 15.9/35.0/64.1 | 0% | 6% | 3/3/4 |
| average | strong | 90% / 70% | 30.1% | 2.5/3.7/5.6 | 0% | 54% | 5/6/8 |
| average | middle | 80% / 45% | 7.5% | 4.7/8.5/14.7 | 0% | 24% | 3/4/6 |
| average | struggling | 70% / 25% | 1.4% | 13.3/29.9/56.5 | 0% | 7% | 3/3/4 |

## Whole-run mGBA harness health

| tier | runs | furthest stage median | died | stalled (pilot lost) | hang | timeout |
|---|---|---|---|---|---|---|
| bot | 5 | 1 | 0 | 5 | 0 | 0 |
| average | 5 | 1 | 0 | 5 | 0 | 0 |
| nonexpert | 5 | 1 | 0 | 5 | 0 | 0 |

