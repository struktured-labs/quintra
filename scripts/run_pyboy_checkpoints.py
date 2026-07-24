#!/usr/bin/env python3
"""Run a controller-only Quintra pilot and save a new state every five minutes."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from importlib.metadata import version
from pathlib import Path

from quintra_pyboy_env import (
    ACTION_A, ACTION_B, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT, ACTION_UP,
    DEFAULT_ROM, QuintraPyBoyEnv,
)


ROOT = Path(__file__).resolve().parent.parent
ROOM_W, ROOM_H = 20, 17
SCREEN_ROOM = 5
DIR_ACTIONS = (ACTION_UP, ACTION_RIGHT, ACTION_DOWN, ACTION_LEFT)
WALKABLE = {1, 3, 7, *range(9, 21), 23, 31, 33, 34, 35, 36,
            *range(55, 64)}  # screen-scale boss BG projections are visual space
FULL_BODY_BLOCKERS = {21, 25, 28, 29, 30}
ENTRY_STATE_RE = re.compile(
    r"quintra-stage-(\d{2})-entry-([a-z]+)(-easy)?\.pyboy$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def axis_action(dx: int, dy: int, *, away: bool = False) -> int:
    if abs(dx) >= abs(dy):
        right = dx >= 0
        if away:
            right = not right
        return ACTION_RIGHT if right else ACTION_LEFT
    down = dy >= 0
    if away:
        down = not down
    return ACTION_DOWN if down else ACTION_UP


def grid_step_action(obs: dict, start: tuple[int, int],
                     dx: int, dy: int) -> int:
    """Align the 12px feet box before following a tile-grid BFS edge."""
    tiles = [tile & 0x7F for tile in obs["tiles"]]

    def pose_open(px: int, py: int) -> bool:
        probes = ((px + 2, py + 8), (px + 13, py + 8),
                  (px + 2, py + 15), (px + 13, py + 15))
        if any(not (0 <= x < ROOM_W * 8 and 0 <= y < ROOM_H * 8)
               or tiles[(y // 8) * ROOM_W + x // 8] not in WALKABLE
               for x, y in probes):
            return False
        body = ((px + 2, py), (px + 13, py),
                (px + 2, py + 7), (px + 13, py + 7))
        return all(not (0 <= x < ROOM_W * 8 and 0 <= y < ROOM_H * 8)
                   or tiles[(y // 8) * ROOM_W + x // 8]
                   not in FULL_BODY_BLOCKERS for x, y in body)

    if dy:
        targets = (start[0] * 8 - 2, (start[0] + 1) * 8 - 2)
        target_x = min((x for x in targets if pose_open(x, obs["y"])),
                       key=lambda x: abs(x - obs["x"]), default=targets[0])
        if obs["x"] != target_x:
            return ACTION_RIGHT if obs["x"] < target_x else ACTION_LEFT
    if dx:
        targets = (start[1] * 8 - 8, (start[1] + 1) * 8 - 8)
        target_y = min((y for y in targets if pose_open(obs["x"], y)),
                       key=lambda y: abs(y - obs["y"]), default=targets[0])
        if obs["y"] != target_y:
            return ACTION_DOWN if obs["y"] < target_y else ACTION_UP
    return axis_action(dx, dy)


def hostile_firing_action(obs: dict, enemy: dict, max_range: int,
                          *, player_x: int | None = None,
                          player_y: int | None = None) -> int:
    """Return the cardinal aim for a real, unobstructed weapon lane.

    Quintra has four-way attacks. A diagonal ray may be visually clear but it
    is not a firing lane: combining A with a route step merely shoots along
    that step and inflates the trainer's attack count without hurting the
    target. ``player_x``/``player_y`` describe a candidate top-left pose for
    BFS; omitted values use the champion's current pose.
    """
    tiles = [tile & 0x7F for tile in obs["tiles"]]
    px = obs["x"] if player_x is None else player_x
    py = obs["y"] if player_y is None else player_y
    # Player projectiles begin at +2 with a 7px box. Aim from their centre;
    # enemy entities use a 16px weak point even when a colossal BG projection
    # surrounds it.
    sx, sy = px + 6, py + 6
    ex, ey = enemy["x"] + 8, enemy["y"] + 8
    dx, dy = ex - sx, ey - sy

    candidates = []
    if 0 < abs(dx) <= max_range and abs(dy) <= 9:
        candidates.append((abs(dy), ACTION_RIGHT if dx > 0 else ACTION_LEFT,
                           ex, sy))
    if 0 < abs(dy) <= max_range and abs(dx) <= 9:
        candidates.append((abs(dx), ACTION_DOWN if dy > 0 else ACTION_UP,
                           sx, ey))
    if not candidates:
        return 0

    for _, action, tx, ty in sorted(candidates):
        distance = max(abs(tx - sx), abs(ty - sy))
        steps = max(1, distance // 4)
        clear = True
        for step in range(1, steps):
            ray_x = sx + (tx - sx) * step // steps
            ray_y = sy + (ty - sy) * step // steps
            tile_x, tile_y = ray_x // 8, ray_y // 8
            if not (0 <= tile_x < ROOM_W and 0 <= tile_y < ROOM_H
                    and tiles[tile_y * ROOM_W + tile_x] in WALKABLE):
                clear = False
                break
        if clear:
            return action
    return 0


def pose_open(obs: dict, px: int, py: int) -> bool:
    """Match the trainer's champion-sized wall probes for a candidate pose."""
    tiles = [tile & 0x7F for tile in obs["tiles"]]
    feet = ((px + 2, py + 8), (px + 13, py + 8),
            (px + 2, py + 15), (px + 13, py + 15))
    if any(not (0 <= x < ROOM_W * 8 and 0 <= y < ROOM_H * 8)
           or tiles[(y // 8) * ROOM_W + x // 8] not in WALKABLE
           for x, y in feet):
        return False
    body = ((px + 2, py), (px + 13, py),
            (px + 2, py + 7), (px + 13, py + 7))
    return all(not (0 <= x < ROOM_W * 8 and 0 <= y < ROOM_H * 8)
               or tiles[(y // 8) * ROOM_W + x // 8]
               not in FULL_BODY_BLOCKERS for x, y in body)


def giant_orbit_action(obs: dict, enemy: dict, aim: int) -> int:
    """Sidestep a colossal body instead of backing into an arena wall."""
    px, py = obs["x"], obs["y"]
    if aim in (ACTION_LEFT, ACTION_RIGHT):
        choices = ((ACTION_UP, 0, -1), (ACTION_DOWN, 0, 1)) \
            if py > 60 else ((ACTION_DOWN, 0, 1), (ACTION_UP, 0, -1))
    else:
        choices = ((ACTION_LEFT, -1, 0), (ACTION_RIGHT, 1, 0)) \
            if px > 72 else ((ACTION_RIGHT, 1, 0), (ACTION_LEFT, -1, 0))
    retreat = {
        ACTION_UP: (ACTION_DOWN, 0, 1),
        ACTION_DOWN: (ACTION_UP, 0, -1),
        ACTION_LEFT: (ACTION_RIGHT, 1, 0),
        ACTION_RIGHT: (ACTION_LEFT, -1, 0),
    }[aim]
    for action, step_x, step_y in (*choices, retreat):
        if pose_open(obs, px + step_x, py + step_y):
            return action
    return retreat[0]


def ordinary_retreat_action(obs: dict, enemy: dict) -> int:
    """Back away from a body threat without repeatedly walking into a wall.

    The ordinary-room audit used to return the direct away direction even when
    the champion's feet were already flush with scenery.  Fast contact enemies
    could then drain an entire heart bar while the policy held a visibly dead
    input.  Try that honest retreat first, then strafe toward the room's open
    half.  This observes only the same current tile/body positions a player can
    see and does not predict procgen or future AI state.
    """
    px, py = obs["x"], obs["y"]
    dx, dy = enemy["x"] - px, enemy["y"] - py
    away = axis_action(dx, dy, away=True)
    if abs(dx) >= abs(dy):
        sidesteps = (ACTION_DOWN, ACTION_UP) if py < 60 \
            else (ACTION_UP, ACTION_DOWN)
    else:
        sidesteps = (ACTION_RIGHT, ACTION_LEFT) if px < 72 \
            else (ACTION_LEFT, ACTION_RIGHT)
    deltas = {
        ACTION_UP: (0, -1), ACTION_RIGHT: (1, 0),
        ACTION_DOWN: (0, 1), ACTION_LEFT: (-1, 0),
    }
    for action in (away, *sidesteps):
        step_x, step_y = deltas[action]
        if pose_open(obs, px + step_x, py + step_y):
            return action
    return away


def route_to_exit(obs: dict, elapsed: int) -> int:
    """Path a champion-sized footprint to a non-return boundary door."""
    tiles = [tile & 0x7F for tile in obs["tiles"]]

    def body_open(x: int, y: int) -> bool:
        return (0 <= x < ROOM_W - 1 and 0 <= y < ROOM_H - 1
                and all(tiles[yy * ROOM_W + xx] in WALKABLE
                        for xx, yy in ((x, y), (x + 1, y),
                                       (x, y + 1), (x + 1, y + 1))))

    edge_goals = {
        0: [(x, 1) for x in (9, 10) if tiles[x] == 3],
        1: [(18, y) for y in (8, 9) if tiles[y * ROOM_W + 19] == 3],
        2: [(x, 15) for x in (9, 10) if tiles[16 * ROOM_W + x] == 3],
        3: [(0, y) for y in (8, 9) if tiles[y * ROOM_W] == 3],
    }
    entered = obs.get("entered_from", 0xFF)
    back = ((entered + 2) & 3) if entered != 0xFF else 0xFF
    candidates = [direction for direction in range(4)
                  if direction != back and edge_goals[direction]]
    if not candidates:
        candidates = [direction for direction in range(4)
                      if edge_goals[direction]]
    if not candidates:
        return (ACTION_RIGHT, ACTION_DOWN, ACTION_LEFT, ACTION_UP)[
            (elapsed // 240) & 3]
    direction = candidates[(elapsed // 900) % len(candidates)]
    goals = set(edge_goals[direction])
    start = (max(0, min(18, (obs["x"] + 2) // 8)),
             max(0, min(15, (obs["y"] + 8) // 8)))
    if start in goals:
        dx, dy = ((0, -1), (1, 0), (0, 1), (-1, 0))[direction]
        return grid_step_action(obs, start, dx, dy)

    queue = [start]
    parent = {start: None}
    found = None
    for current in queue:
        if current in goals:
            found = current
            break
        x, y = current
        for nx, ny in ((x, y - 1), (x + 1, y),
                       (x, y + 1), (x - 1, y)):
            nxt = (nx, ny)
            vertical_blocked = (ny != y and ny > 0
                                and any(tiles[(ny - 1) * ROOM_W + xx]
                                        in FULL_BODY_BLOCKERS
                                        for xx in (nx, nx + 1)))
            if nxt not in parent and body_open(nx, ny) and not vertical_blocked:
                parent[nxt] = current
                queue.append(nxt)
    if found is None:
        goal = min(goals, key=lambda item: abs(item[0] - start[0])
                   + abs(item[1] - start[1]))
        return axis_action(goal[0] - start[0], goal[1] - start[1])
    while parent[found] != start:
        found = parent[found]
    dx, dy = found[0] - start[0], found[1] - start[1]
    return grid_step_action(obs, start, dx, dy)


def route_to_hostile(obs: dict, enemy: dict, max_range: int = 30) -> int:
    """Walk around hard cover until the primary attack has a clear lane."""
    tiles = [tile & 0x7F for tile in obs["tiles"]]

    def body_open(x: int, y: int) -> bool:
        return (0 <= x < ROOM_W - 1 and 0 <= y < ROOM_H - 1
                and all(tiles[yy * ROOM_W + xx] in WALKABLE
                        for xx, yy in ((x, y), (x + 1, y),
                                       (x, y + 1), (x + 1, y + 1))))

    start = (max(0, min(18, (obs["x"] + 2) // 8)),
             max(0, min(15, (obs["y"] + 8) // 8)))
    goals = {(x, y) for y in range(ROOM_H - 1) for x in range(ROOM_W - 1)
             if body_open(x, y)
             and hostile_firing_action(obs, enemy, max_range,
                                       player_x=x * 8 - 2,
                                       player_y=y * 8 - 8)}
    if not goals:
        return axis_action(enemy["x"] - obs["x"], enemy["y"] - obs["y"])
    if start in goals:
        # The caller owns the separate aim/fire beat once a real cardinal lane
        # exists. Do not walk out of it here.
        return 0

    queue = [start]
    parent = {start: None}
    found = None
    for current in queue:
        if current in goals:
            found = current
            break
        x, y = current
        for nx, ny in ((x, y - 1), (x + 1, y),
                       (x, y + 1), (x - 1, y)):
            nxt = (nx, ny)
            vertical_blocked = (ny != y and ny > 0
                                and any(tiles[(ny - 1) * ROOM_W + xx]
                                        in FULL_BODY_BLOCKERS
                                        for xx in (nx, nx + 1)))
            if nxt not in parent and body_open(nx, ny) and not vertical_blocked:
                parent[nxt] = current
                queue.append(nxt)
    if found is None:
        return axis_action(enemy["x"] - obs["x"], enemy["y"] - obs["y"])
    while parent[found] != start:
        found = parent[found]
    return grid_step_action(obs, start, found[0] - start[0], found[1] - start[1])


def route_to_pickup(obs: dict, pickup: dict) -> int:
    """Reach the walk-over pose for a visible Sigil without crossing cover."""
    tiles = [tile & 0x7F for tile in obs["tiles"]]

    def body_open(x: int, y: int) -> bool:
        return (0 <= x < ROOM_W - 1 and 0 <= y < ROOM_H - 1
                and all(tiles[yy * ROOM_W + xx] in WALKABLE
                        for xx, yy in ((x, y), (x + 1, y),
                                       (x, y + 1), (x + 1, y + 1))))

    goals = set()
    for y in range(ROOM_H - 1):
        for x in range(ROOM_W - 1):
            px, py = x * 8 - 2, y * 8 - 8
            # The cartridge's pickup box is the 12x8 feet rectangle against
            # the fixture's 6x6 body. Choose any aligned, physically open pose
            # that overlaps it instead of assuming its center is standable.
            if (body_open(x, y) and px + 14 > pickup["x"]
                    and px + 2 < pickup["x"] + 6
                    and py + 16 > pickup["y"]
                    and py + 8 < pickup["y"] + 6):
                goals.add((x, y))
    start = (max(0, min(18, (obs["x"] + 2) // 8)),
             max(0, min(15, (obs["y"] + 8) // 8)))
    if start in goals:
        target_x, target_y = start[0] * 8 - 2, start[1] * 8 - 8
        return axis_action(target_x - obs["x"], target_y - obs["y"])
    queue = [start]
    parent = {start: None}
    found = None
    for current in queue:
        if current in goals:
            found = current
            break
        x, y = current
        for nx, ny in ((x, y - 1), (x + 1, y),
                       (x, y + 1), (x - 1, y)):
            nxt = (nx, ny)
            vertical_blocked = (ny != y and ny > 0
                                and any(tiles[(ny - 1) * ROOM_W + xx]
                                        in FULL_BODY_BLOCKERS
                                        for xx in (nx, nx + 1)))
            if nxt not in parent and body_open(nx, ny) and not vertical_blocked:
                parent[nxt] = current
                queue.append(nxt)
    if found is None:
        return axis_action(pickup["x"] - obs["x"], pickup["y"] - obs["y"])
    while parent[found] != start:
        found = parent[found]
    return grid_step_action(obs, start, found[0] - start[0], found[1] - start[1])


def controller_action(obs: dict, elapsed: int) -> int:
    """Small deterministic survival/combat pilot; no WRAM writes or warps."""
    px, py = obs["x"], obs["y"]
    class_id = obs["class_id"]
    # Public projectile velocity is enough to distinguish an approaching lane
    # from harmless nearby traffic. Dodge perpendicular to the first predicted
    # hurtbox crossing; moving directly away along a shot's own axis merely
    # kept the old pilot trapped in front of it.
    threats = []
    for shot in obs["projectiles"]:
        # A speed-two ring launched from 50px away reaches the champion in
        # roughly 25 frames. The former 12-frame horizon did not react until
        # a base-speed vessel had too little room to clear its own hurtbox.
        # Thirty frames reads the same telegraphed lane a human can already
        # see without exposing future or off-screen state.
        for eta in range(1, 31):
            sx = shot["x"] + shot["vx"] * eta
            sy = shot["y"] + shot["vy"] * eta
            if sx + 6 > px + 4 and sx < px + 12 and sy + 6 > py + 5 and sy < py + 13:
                threats.append((eta, shot))
                break
    if threats:
        _, shot = min(threats, key=lambda item: item[0])
        if abs(shot["vx"]) >= abs(shot["vy"]):
            dodge = ACTION_DOWN if shot["y"] < py + 8 else ACTION_UP
        else:
            dodge = ACTION_RIGHT if shot["x"] < px + 8 else ACTION_LEFT
        # Sauran and Picsean own genuine B-button barriers. Use the edge alone
        # when a lane is imminent; A+B while A was already held activated
        # neither the signature nor Convergence under the cartridge's edge
        # semantics.
        if (class_id in (1, 3) and obs["active_charge"] == 0
                and obs["shield_timer"] == 0 and obs["mp"] >= 2):
            return dodge | ACTION_B
        return dodge
    if obs["hostiles"]:
        enemy = min(obs["hostiles"],
                    key=lambda item: abs(item["x"] - px) + abs(item["y"] - py))
        dx, dy = enemy["x"] - px, enemy["y"] - py
        reach = max(abs(dx), abs(dy))
        # These are controller safety lanes, not ROM buffs. They mirror the
        # measured per-class spacing used by the full mGBA victory pilot:
        # Wolfkin can work inside its 64px Fang lane, while ranged kits should
        # not volunteer for colossal body contact.
        retreat_ranges = (24, 48, 48, 56, 36)
        # Tail Spike and Stinger travel 48px from a near-body origin. Holding
        # them at a nominal 48–52px center distance produced visually aligned
        # attacks that expired just before the weak point. Keep their firing
        # poses inside that physical lane; ranged kits retain room-scale space.
        fire_ranges = (64, 52, 96, 96, 52)
        if reach < retreat_ranges[class_id]:
            if enemy.get("giant"):
                aim = axis_action(dx, dy)
                lane = hostile_firing_action(
                    obs, enemy, fire_ranges[class_id])
                # A brief aimed beat inside the orbit preserves pressure while
                # the remaining beats sidestep the body. This is the same
                # ordinary attack/orbit rhythm that clears the fixed mGBA run.
                if lane and elapsed % (3 if class_id == 0 else 2) == 0:
                    return lane | ACTION_A
                return giant_orbit_action(obs, enemy, aim)
            # Corvin and Picsean are room-range attackers. Four contact
            # enemies can keep them permanently inside their preferred
            # spacing; blindly retreating then records zero damage while the
            # pilot scrapes the boundary until death. When a real cardinal
            # lane is already open, spend one beat in four facing/firing and
            # use the other three to preserve space. This is ordinary
            # controller kiting, not hidden aim or a cartridge-side assist.
            lane = hostile_firing_action(obs, enemy, fire_ranges[class_id])
            if class_id in (2, 3) and lane and elapsed % 4 == 0:
                return lane | ACTION_A
            # Retreating while holding A aims the attack away from the target.
            # Preserve spacing first, then reacquire a cardinal lane.
            return ordinary_retreat_action(obs, enemy)

        aim = hostile_firing_action(obs, enemy, fire_ranges[class_id])
        if not aim:
            # Approaching and attacking cannot share a beat unless the route
            # direction also happens to be the firing direction. Keeping them
            # separate makes controller telemetry honest and avoids spraying
            # into cover while navigating around it.
            return route_to_hostile(obs, enemy, fire_ranges[class_id])

        if (elapsed % 180 < 4 and obs["active_charge"] == 0
                and obs["mp"] >= 2):
            return aim | ACTION_B
        if elapsed % 24 < 4:
            # Refresh facing after a dodge or path step. Neutral A beats below
            # preserve the lane without continuously walking into the boss.
            return aim | ACTION_A
        return ACTION_A
    sigils = [pickup for pickup in obs.get("pickups", [])
              if pickup["kind"] == 11]
    if sigils:
        sigil = min(sigils, key=lambda item: abs(item["x"] - px)
                    + abs(item["y"] - py))
        return route_to_pickup(obs, sigil)
    return route_to_exit(obs, elapsed) | ACTION_A


def settle_checkpoint(env: QuintraPyBoyEnv, obs: dict) -> tuple[dict, int]:
    """Release input and wait for an atomic, fully generated room frame."""
    stable = 0
    advanced = 0
    context = None
    while advanced < 240:
        obs, _, terminal, _ = env.step(0, 1)
        advanced += 1
        current = (obs["screen"], obs["room"], obs["world_mode"],
                   obs["world_screen"])
        generated = (obs["screen"] == SCREEN_ROOM
                     and not any(tile & 0x80 for tile in obs["tiles"]))
        stable = stable + 1 if generated and current == context else 0
        context = current
        if terminal:
            return obs, advanced
        if stable >= 8:
            return obs, advanced
    raise RuntimeError("checkpoint never reached a stable generated room")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--out", type=Path, default=ROOT / "tmp/timed-states")
    parser.add_argument("--state", type=Path,
                        help="manifest-backed starting checkpoint")
    parser.add_argument("--class-id", type=int, default=0)
    parser.add_argument("--difficulty", choices=("normal", "easy"), default="easy")
    parser.add_argument("--minutes", type=int, default=30,
                        help="total emulated minutes (default: 30)")
    parser.add_argument("--checkpoint-minutes", type=int, default=5,
                        help="emulated minutes per new state (default: 5)")
    parser.add_argument("--total-frames", type=int,
                        help=argparse.SUPPRESS)
    parser.add_argument("--checkpoint-frames", type=int,
                        help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.rom = args.rom.resolve()
    total_frames = args.total_frames or args.minutes * 60 * 60
    checkpoint_frames = args.checkpoint_frames or args.checkpoint_minutes * 60 * 60
    if total_frames < 1 or checkpoint_frames < 1:
        parser.error("frame/minute durations must be positive")

    args.out.mkdir(parents=True, exist_ok=True)
    env = QuintraPyBoyEnv(args.rom)
    active_state = args.state
    curriculum_match = ENTRY_STATE_RE.fullmatch(args.state.name) if args.state else None
    curriculum_stage = int(curriculum_match.group(1)) if curriculum_match else None
    curriculum_champion = curriculum_match.group(2) if curriculum_match else None
    curriculum_suffix = curriculum_match.group(3) or "" if curriculum_match else ""
    curriculum_advances = 0
    last_checkpoint_progress = None

    def restart() -> dict:
        if active_state:
            return env.load_state(active_state)
        return env.reset(args.class_id, difficulty=args.difficulty)

    records = []
    elapsed = 0
    restarts = 0
    next_checkpoint = checkpoint_frames
    try:
        obs = restart()
        while elapsed < total_frames:
            frames = min(4, total_frames - elapsed)
            obs, reward, terminal, info = env.step(controller_action(obs, elapsed), frames)
            elapsed += frames
            if terminal:
                restarts += 1
                obs = restart()
            if elapsed >= next_checkpoint:
                obs, settling_frames = settle_checkpoint(env, obs)
                elapsed += settling_frames
                if env.is_terminal(obs):
                    restarts += 1
                    obs = restart()
                progress = (obs["stage"], obs["room"], obs["bosses"],
                            obs["world_mode"], obs["world_screen"])
                advanced_to = None
                # A five-minute snapshot is not useful when every later file
                # captures the same solved boss room or route lip. If this run
                # began from a manifest-bound stage-entry curriculum and made
                # no forward progression for a whole checkpoint interval,
                # advance to the next matching entry state. Each segment is
                # still played with ordinary controller input; the explicit
                # external-state jump is recorded rather than hidden.
                if (last_checkpoint_progress is not None
                        and progress <= last_checkpoint_progress
                        and curriculum_stage is not None
                        and curriculum_champion is not None):
                    target_stage = max(curriculum_stage + 1, obs["stage"])
                    if target_stage <= 9:
                        candidate = args.state.parent / (
                            f"quintra-stage-{target_stage:02d}-entry-"
                            f"{curriculum_champion}{curriculum_suffix}.pyboy")
                        if candidate.exists():
                            active_state = candidate
                            obs = env.load_state(active_state)
                            curriculum_stage = target_stage
                            curriculum_advances += 1
                            advanced_to = target_stage
                            progress = (obs["stage"], obs["room"], obs["bosses"],
                                        obs["world_mode"], obs["world_screen"])
                last_checkpoint_progress = progress
                label_minutes = next_checkpoint // (60 * 60)
                label = f"{label_minutes:04d}m" if label_minutes else f"{next_checkpoint:06d}f"
                path = env.save_state(args.out / f"quintra-training-{label}.pyboy")
                obs = env.observe()
                records.append({
                    "file": path.name,
                    "sha256": sha256(path),
                    "scheduled_frames": next_checkpoint,
                    "elapsed_frames": elapsed,
                    "stage": obs["stage"],
                    "room_counter": obs["room"],
                    "difficulty": obs["difficulty"],
                    "class_id": obs["class_id"],
                    "hp": obs["hp"],
                    "restarts": restarts,
                    "curriculum_advance": advanced_to,
                })
                print(f"[timed-states] {label}: stage {obs['stage']} room {obs['room']} "
                      f"HP {obs['hp']}/{obs['hp_max']}"
                      f"{' advance=' + str(advanced_to) if advanced_to else ''}"
                      f" -> {path}")
                next_checkpoint += checkpoint_frames
    finally:
        env.close()

    manifest = {
        "format": "PyBoy save_state",
        "pyboy_version": version("pyboy"),
        "rom": args.rom.name,
        "rom_sha256": sha256(args.rom),
        "checkpoint_interval_frames": checkpoint_frames,
        "source_state": str(args.state) if args.state else None,
        "source_state_sha256": sha256(args.state) if args.state else None,
        "policy_sha256": sha256(Path(__file__)),
        "starting_difficulty": args.difficulty if not args.state else None,
        "restarts": restarts,
        "curriculum_advances": curriculum_advances,
        "stall_advance_enabled": bool(curriculum_match),
        "states": records,
    }
    manifest_path = args.out / "manifest.json"
    temp = manifest_path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(manifest, indent=2) + "\n")
    temp.replace(manifest_path)

    # Publication is not complete until every manifest-bound file restores in
    # a fresh emulator with its recorded player-visible context. This catches
    # truncated state writes and stale ROM/PyBoy metadata immediately instead
    # of handing the tester a broken five-minute checkpoint.
    verifier = QuintraPyBoyEnv(args.rom)
    try:
        for record in records:
            restored = verifier.load_state(args.out / record["file"])
            if (restored["stage"] != record["stage"]
                    or restored["room"] != record["room_counter"]
                    or restored["difficulty"] != record["difficulty"]
                    or restored["class_id"] != record["class_id"]
                    or restored["hp"] <= 0):
                raise RuntimeError(
                    f"periodic checkpoint restored wrong context: {record['file']}")
    finally:
        verifier.close()
    print(f"[timed-states] verified {len(records)} periodic checkpoint(s)")


if __name__ == "__main__":
    main()
