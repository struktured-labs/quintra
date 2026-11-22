<!-- Baseline for scripts/balance_thresholds.json. ROM 68755c1d (main 62b83e51), Normal; `scripts/balance_arena.py --stages 1-9 --seeds 3 --skills bot skilled average nonexpert` plus a bounded mGBA whole-run sample (`balance_sweep.py --mode full --seeds 1 --frames 108000`). -->

> **Read first:** the controller pilot under these tiers cannot yet win Normal Colossus fights that people win (the repo's own `audit_boss_curriculum.py` also scores 0/15 on stages 1-3), so measured win rates and the measured first-clear table are floors. Use the relative signals (boss HP removed, fight length, burst, status timing, spikes) and the scenario table.

# Quintra difficulty report

1080 human-model slices; tiers nonexpert, average, skilled, bot; stages 1-9. Times in seconds unless noted; `median (p25-p75)`. Model numbers are **estimates**.

## Stage 3 Colossus (flagged by playtest)

| tier | fights | win rate | deaths | time-to-kill s (wins) | attempt s | dmg taken | max 2 s burst (% max HP) | burst spikes/fight | boss HP left when lost | mean boss HP removed |
|---|---|---|---|---|---|---|---|---|---|---|
| nonexpert | 15 | 0% | 15 | n/a | 32.2 (22.8-35.7) | 14 (14-15) | 23 (21-33) | 0.0 (0.0-0.0) | 94 (92-97)% | 6% |
| average | 15 | 0% | 15 | n/a | 25.2 (17.4-32.2) | 14 (14-14) | 31 (25-36) | 0.0 (0.0-0.0) | 94 (92-95)% | 7% |
| skilled | 15 | 0% | 15 | n/a | 25.4 (19.9-32.3) | 14 (14-14) | 29 (21-31) | 0.0 (0.0-0.0) | 92 (90-95)% | 8% |
| bot | 15 | 0% | 15 | n/a | 26.4 (18.8-30.7) | 14 (14-14) | 29 (21-29) | 0.0 (0.0-0.0) | 92 (90-93)% | 9% |

## Status effects at bad moments

| tier | harmful landings | per boss-minute | in boss fights | at low HP (≤1/3) | deaths | deaths after status ≤3 s | ≤5 s | ≤10 s | play time within 5 s of a status | lift (≤5 s share / exposure) |
|---|---|---|---|---|---|---|---|---|---|---|
| nonexpert | 96 | 0.00 | 0 | 15 | 162 | 6/162 (4%) | 7/162 (4%) | 7/162 (4%) | 5% | 0.80x |
| average | 83 | 0.00 | 0 | 16 | 159 | 4/159 (3%) | 5/159 (3%) | 5/159 (3%) | 4% | 0.76x |
| skilled | 95 | 0.00 | 0 | 24 | 160 | 6/160 (4%) | 8/160 (5%) | 8/160 (5%) | 4% | 1.14x |
| bot | 73 | 0.00 | 0 | 11 | 155 | 2/155 (1%) | 4/155 (3%) | 4/155 (3%) | 4% | 0.70x |

Lift compares the share of deaths that follow a status with the share of play time spent under or just after one: about 1x means statuses are along for the ride; well above 1x means they cause deaths.

Deaths within 5 s of a harmful status, by effect (all tiers): blind 18, bleed 3, stop 2, mute 1

| stage | deaths | after status ≤5 s |
|---|---|---|
| 1 | 61 | 3 (5%) |
| 2 | 86 | 0 (0%) |
| 3 | 99 | 0 (0%) |
| 4 | 60 | 0 (0%) |
| 5 | 60 | 0 (0%) |
| 6 | 79 | 18 (23%) |
| 7 | 72 | 0 (0%) |
| 8 | 59 | 3 (5%) |
| 9 | 60 | 0 (0%) |

All status landings by type: blind 212, mute 60, bleed 53, haste 27, stop 22

## Difficulty curve by stage

Boss: Colossus fight from its live arena checkpoint. Room: the stage's first combat room at full HP.

### nonexpert

| stage | boss win | boss TTK s | boss attempt s | boss dmg | room death | room clear s | room dmg/min | dealt:taken | est. stage min | est. P(pass stage) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0/15 | n/a | 51.8 (38.9-61.2) | 14 (14-14) | 1/1 | 48.3 (48.3-48.3) | 16.2 (16.2-16.2) | 0.8 (0.8-0.8) | 17.6 | 0% |
| 2 | 0/15 | n/a | 22.6 (19.7-26.3) | 14 (14-14) | 7/7 | 14.6 (14.1-27.3) | 57.6 (31.9-64.6) | 0.9 (0.3-2.2) | 11.4 | 0% |
| 3 | 0/15 | n/a | 32.2 (22.8-35.7) | 14 (14-15) | 12/12 | 35.2 (31.5-49.4) | 24.9 (19.7-28.2) | 10.1 (6.8-11.5) | 15.5 | 0% |
| 4 | 0/15 | n/a | 58.4 (21.6-64.7) | 15 (15-15) | 0/2 | 49.4 (46.6-52.2) | 3.1 (2.7-3.6) | 64.2 (56.6-71.9) | 20.4 | 0% |
| 5 | 0/15 | n/a | 26.7 (21.9-32.0) | 15 (15-15) | 0/0 | n/a | n/a | n/a | 19.0 | 2% |
| 6 | 0/15 | n/a | 17.1 (12.8-20.8) | 15 (15-15) | 5/5 | 37.4 (32.0-39.0) | 28.9 (26.2-29.2) | 0.0 (0.0-0.9) | 19.8 | 0% |
| 7 | 0/15 | n/a | 9.7 (8.2-11.3) | 16 (16-16) | 2/3 | 36.1 (31.6-45.4) | 33.2 (18.8-36.5) | 5.6 (2.8-53.9) | 18.1 | 0% |
| 8 | 1/15 | 40.5 (40.5-40.5) | 30.3 (24.7-41.8) | 16 (16-16) | 1/1 | 44.5 (44.5-44.5) | 21.6 (21.6-21.6) | 2.1 (2.1-2.1) | 22.0 | 0% |
| 9 | 0/15 | n/a | 28.6 (27.4-41.5) | 16 (16-16) | 0/11 | 12.3 (9.1-24.5) | 0.0 (0.0-0.0) | 0.0 (0.0-10.0) | 15.2 | 1% |

### average

| stage | boss win | boss TTK s | boss attempt s | boss dmg | room death | room clear s | room dmg/min | dealt:taken | est. stage min | est. P(pass stage) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0/15 | n/a | 60.2 (40.0-72.0) | 14 (14-14) | 0/0 | n/a | n/a | n/a | 14.6 | 2% |
| 2 | 0/15 | n/a | 21.9 (20.0-26.4) | 14 (14-14) | 7/7 | 15.7 (14.4-17.8) | 57.0 (43.8-63.4) | 1.9 (0.3-2.7) | 9.9 | 0% |
| 3 | 0/15 | n/a | 25.2 (17.4-32.2) | 14 (14-14) | 9/9 | 36.5 (32.1-38.1) | 24.3 (20.5-26.3) | 10.0 (5.8-15.0) | 13.9 | 0% |
| 4 | 0/15 | n/a | 37.1 (29.6-46.1) | 15 (15-15) | 0/1 | 48.6 (48.6-48.6) | 1.2 (1.2-1.2) | 162.0 (162.0-162.0) | 18.2 | 0% |
| 5 | 0/15 | n/a | 22.2 (19.2-24.2) | 15 (15-15) | 0/0 | n/a | n/a | n/a | 17.2 | 2% |
| 6 | 0/15 | n/a | 14.3 (10.2-18.9) | 15 (15-15) | 5/6 | 31.8 (27.6-34.1) | 30.6 (27.3-32.0) | 0.7 (0.6-2.0) | 16.6 | 0% |
| 7 | 0/15 | n/a | 9.0 (7.9-11.6) | 16 (16-16) | 4/4 | 31.6 (28.2-35.8) | 33.2 (30.3-37.9) | 5.4 (3.5-7.6) | 15.3 | 0% |
| 8 | 1/15 | 28.5 (28.5-28.5) | 29.6 (25.4-39.2) | 16 (16-16) | 0/0 | n/a | n/a | n/a | 18.9 | 6% |
| 9 | 0/15 | n/a | 27.2 (21.2-39.7) | 16 (16-16) | 0/10 | 12.9 (11.0-25.4) | 0.0 (0.0-0.0) | 1.5 (0.0-12.2) | 13.7 | 1% |

### skilled

| stage | boss win | boss TTK s | boss attempt s | boss dmg | room death | room clear s | room dmg/min | dealt:taken | est. stage min | est. P(pass stage) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0/15 | n/a | 78.2 (64.8-87.5) | 14 (14-14) | 2/2 | 45.4 (41.8-48.9) | 20.8 (17.8-23.7) | 1.4 (1.2-1.7) | 14.5 | 0% |
| 2 | 0/15 | n/a | 21.3 (19.8-25.8) | 14 (14-14) | 5/5 | 15.7 (14.1-16.6) | 57.2 (55.2-57.9) | 0.6 (0.4-1.3) | 8.6 | 0% |
| 3 | 0/15 | n/a | 25.4 (19.9-32.3) | 14 (14-14) | 9/9 | 33.0 (17.9-35.4) | 25.5 (23.7-43.7) | 4.9 (3.2-11.4) | 11.9 | 0% |
| 4 | 0/15 | n/a | 38.0 (33.1-58.4) | 15 (15-15) | 0/0 | n/a | n/a | n/a | 15.0 | 2% |
| 5 | 0/15 | n/a | 23.2 (20.4-28.3) | 15 (15-15) | 0/1 | 42.0 (42.0-42.0) | 1.4 (1.4-1.4) | 293.0 (293.0-293.0) | 16.4 | 0% |
| 6 | 0/15 | n/a | 11.6 (10.7-15.0) | 15 (15-15) | 5/5 | 35.1 (21.9-39.2) | 29.1 (26.0-46.6) | 0.0 (0.0-0.8) | 16.1 | 0% |
| 7 | 0/15 | n/a | 9.1 (7.7-10.3) | 16 (16-16) | 3/3 | 31.7 (29.7-32.4) | 32.6 (32.4-35.8) | 3.5 (3.2-6.4) | 13.9 | 0% |
| 8 | 1/15 | 26.9 (26.9-26.9) | 27.2 (24.9-29.7) | 16 (16-16) | 2/2 | 43.2 (39.1-47.4) | 25.0 (21.3-28.8) | 3.8 (3.6-4.1) | 18.4 | 0% |
| 9 | 0/15 | n/a | 27.1 (22.5-32.4) | 16 (16-16) | 0/10 | 14.5 (8.1-22.3) | 0.0 (0.0-0.0) | 4.5 (0.0-13.0) | 12.9 | 1% |

### bot

| stage | boss win | boss TTK s | boss attempt s | boss dmg | room death | room clear s | room dmg/min | dealt:taken | est. stage min | est. P(pass stage) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1/15 | 69.6 (69.6-69.6) | 80.1 (68.3-85.1) | 14 (14-14) | 0/0 | n/a | n/a | n/a | 12.7 | 7% |
| 2 | 0/15 | n/a | 25.9 (23.0-27.2) | 14 (14-14) | 7/7 | 16.2 (16.1-48.9) | 50.9 (16.6-59.4) | 2.8 (0.9-3.4) | 8.1 | 0% |
| 3 | 0/15 | n/a | 26.4 (18.8-30.7) | 14 (14-14) | 9/9 | 25.7 (21.6-32.8) | 32.7 (26.7-38.5) | 6.3 (3.6-10.7) | 9.9 | 0% |
| 4 | 0/15 | n/a | 41.6 (26.9-76.9) | 15 (15-15) | 0/0 | n/a | n/a | n/a | 14.4 | 2% |
| 5 | 0/15 | n/a | 24.4 (22.2-31.6) | 15 (15-15) | 0/2 | 38.6 (38.3-38.8) | 0.0 (0.0-0.0) | 267.5 (264.8-270.2) | 14.9 | 0% |
| 6 | 0/15 | n/a | 11.3 (8.8-13.2) | 15 (15-15) | 4/4 | 43.6 (39.9-46.5) | 23.3 (19.3-27.2) | 1.9 (1.3-2.7) | 17.7 | 0% |
| 7 | 0/15 | n/a | 8.6 (7.7-10.5) | 16 (16-16) | 3/3 | 31.9 (27.9-42.1) | 32.0 (26.9-38.6) | 2.9 (2.7-5.9) | 13.3 | 0% |
| 8 | 1/15 | 31.4 (31.4-31.4) | 31.9 (29.2-39.6) | 16 (16-16) | 0/0 | n/a | n/a | n/a | 16.9 | 6% |
| 9 | 0/15 | n/a | 27.6 (22.2-41.7) | 16 (16-16) | 0/10 | 14.8 (11.1-27.2) | 0.0 (0.0-0.0) | 0.0 (0.0-13.0) | 12.4 | 1% |

## Spikes (> 2x neighbour mean)

- nonexpert: stage 8 room death rate 1.00 vs neighbours 0.33
- nonexpert: stage 3 boss HP removed 6% vs neighbours 18%
- nonexpert: stage 9 boss HP removed 8% vs neighbours 51%
- average: stage 3 boss HP removed 7% vs neighbours 25%
- average: stage 9 boss HP removed 13% vs neighbours 58%
- skilled: stage 3 boss HP removed 8% vs neighbours 34%
- skilled: stage 9 boss HP removed 13% vs neighbours 51%
- bot: stage 3 boss HP removed 9% vs neighbours 29%
- bot: stage 9 boss HP removed 19% vs neighbours 58%

## Estimated human first clear (death wipes the run)

| tier | P(clear one run) | clean-run length min | runs to first clear | first-clear hours, no learning | with learning | players clearing within 2 h | 2 h as share of median first-clear time | furthest stage by 2 h |
|---|---|---|---|---|---|---|---|---|
| nonexpert | 0.00% | 159 | 692/739/820 | >200/>200/>200 | >200/>200/>200 | 0% | 0% | 1/1/1 |
| average | 0.00% | 138 | 811/869/966 | >200/>200/>200 | >200/>200/>200 | 0% | 0% | 1/1/1 |
| skilled | 0.00% | 128 | 821/874/969 | >200/>200/>200 | >200/>200/>200 | 0% | 0% | 1/1/1 |
| bot | 0.00% | 120 | 905/973/1084 | >200/>200/>200 | >200/>200/>200 | 0% | 0% | 1/1/2 |

Hours are p25/median/p75 over simulated players; each player draws its own odds from the measured win/death counts, so thin samples widen the range. *Learning* moves each stage's pass odds 10% of the way toward the next tier per visit to that stage. Slices start rooms and the Colossus at the checkpoint's HP, so attrition between rooms is not modelled: treat the hours as a lower bound. Stage time = combat rooms x measured room time + transit 12s/room + puzzles + Riftwild leg + boss; path rooms come from the cartridge topology x 1.6 detour factor.

## First clear under assumed human pass odds (scenario, not measured)

Stage lengths are measured per tier above; pass odds are assumptions because the pilot cannot yet win Normal Colossus fights a person wins.

| tier times | scenario | P(pass stage) / stage 3 | P(clear one run) | first-clear hours p25/median/p75 | players clearing within 2 h | 2 h as share of median first clear | furthest stage by 2 h p25/median/p75 |
|---|---|---|---|---|---|---|---|
| nonexpert | strong | 90% / 70% | 30.1% | 2.7/3.8/5.8 | 0% | 52% | 5/6/7 |
| nonexpert | middle | 80% / 45% | 7.5% | 4.9/8.6/15.3 | 0% | 23% | 3/4/6 |
| nonexpert | struggling | 70% / 25% | 1.4% | 14.2/31.6/57.8 | 0% | 6% | 3/3/4 |
| average | strong | 90% / 70% | 30.1% | 2.3/3.4/5.0 | 0% | 59% | 5/6/8 |
| average | middle | 80% / 45% | 7.5% | 4.2/7.5/13.1 | 0% | 27% | 3/5/6 |
| average | struggling | 70% / 25% | 1.4% | 11.6/26.2/49.4 | 0% | 8% | 3/3/4 |

## Whole-run mGBA harness health

| tier | runs | furthest stage median | died | stalled (pilot lost) | hang | timeout |
|---|---|---|---|---|---|---|
| bot | 5 | 1 | 0 | 5 | 0 | 0 |
| average | 5 | 1 | 1 | 4 | 0 | 0 |
| nonexpert | 5 | 1 | 1 | 4 | 0 | 0 |

