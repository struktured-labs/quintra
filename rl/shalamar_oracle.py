"""Scripted Shalamar oracle.

Strategy (from user, 2026-05-10):
- Spider mini-boss spawns first in the savestate; godmode_step clears it automatically
- Once in arena (D880=0x0c) with FFBF=0, this is the Shalamar fight
- Hover under Shalamar (align sara_x with boss_x from OAM)
- Spam UP+A (action 8) — sticky aim points up after upward movement
- Move toward target_y ~ 80 (upper area, away from "south end spam")
- Godmode prevents Sara death; DCBB in arena = Shalamar's HP, drains naturally on hit

Success criteria:
- FFBA increments past initial (0 → 1) → stage 1 cleared
- OR D880 transitions to 0x16 (post-boss reload) inside arena

Captures (state_vector, action, kill_event_flag) for downstream BC oversampling.
"""
from __future__ import annotations
import os, sys, time, json
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import numpy as np
import torch
torch.set_num_threads(1)

sys.path.insert(0, "/home/struktured/projects/penta-dragon-dx-claude/rl")
from penta_rl.godmode_env import godmode_step
from penta_rl.env import N_ACTIONS, ACTION_BUTTONS, PentaEnv
from penta_rl.state import vector_dim, read_state, state_to_vector


class ShalamarEnv(PentaEnv):
    """PentaEnv that injects godmode per tick and terminates only on real progression."""

    def step(self, action: int):
        for b in self._held:
            self.pb.button_release(b)
        self._held = ACTION_BUTTONS[action]
        for b in self._held:
            self.pb.button_press(b)
        for _ in range(self.frame_skip):
            godmode_step(self.pb)
            self.pb.tick()
        self.steps += 1
        s = read_state(self.pb)
        reward, info = self.reward_tracker.step(s, action=action)
        truncated = self.steps >= self.max_steps
        # Termination: FFBA advance or D880→0x16 (post-boss reload) signals stage cleared
        info["state"] = s
        info["steps"] = self.steps
        return state_to_vector(s), reward, False, truncated, info

ROM = "/home/struktured/projects/penta-dragon-dx-claude/rom/Penta Dragon (J) [A-fix].gb"
STATE = "/home/struktured/projects/penta-dragon-dx-claude/rl/saves/user_demo/converted/195329_BOSS1_SHALAMAR_pre_fight.state"
OUT_NPZ = "/home/struktured/projects/penta-dragon-dx-claude/rl/bc_data/expert_shalamar_oracle.npz"
OUT_JSONL = "/home/struktured/projects/penta-dragon-dx-claude/rl/bc_data/expert_shalamar_oracle.jsonl"

# Tunable
EPISODES = 20
MAX_EP_STEPS = 2300         # just past typical kill at ~step 2155
TARGET_Y = 80               # Sara hover y (upper half of screen)
X_ALIGN_TOL = 6             # pixels — how tight to keep sara_x ≈ boss_x

# Actions
A_FIRE = 0        # A
A_UP = 6          # UP
A_UPA = 8         # UP+A
A_DOWN = 7        # DOWN
A_DOWNA = 9       # DOWN+A
A_LEFT = 5        # LEFT
A_RIGHT = 4       # RIGHT


def get_oam_features(pb):
    """Compute Sara + boss centroids from OAM."""
    sara_tiles = {0x00, 0x01, 0x06, 0x09, 0x0A, 0x0F}
    body_min, body_max = 0x30, 0x7F
    sara_x = sara_y = 0; sara_n = 0
    boss_x = boss_y = 0; boss_n = 0
    proj_n = 0
    for i in range(40):
        base = 0xFE00 + i * 4
        y = pb.memory[base]; x = pb.memory[base + 1]; tile = pb.memory[base + 2]
        if y == 0 and x == 0: continue
        screen_y = y - 16; screen_x = x - 8
        if not (0 <= screen_y < 144 and 0 <= screen_x < 160): continue
        if tile in sara_tiles:
            if tile in {0x00, 0x01}:
                proj_n += 1
            else:
                sara_x += screen_x; sara_y += screen_y; sara_n += 1
        elif body_min <= tile <= body_max:
            boss_x += screen_x; boss_y += screen_y; boss_n += 1
    return (
        sara_x // sara_n if sara_n else -1,
        sara_y // sara_n if sara_n else -1,
        boss_x // boss_n if boss_n else -1,
        boss_y // boss_n if boss_n else -1,
        boss_n, proj_n,
    )


def oracle_action(pb, rng=None, target_y=None, x_tol=None):
    """Hand-coded Shalamar oracle: hover-and-fire with optional stochasticity."""
    sara_x, sara_y, boss_x, boss_y, boss_n, proj_n = get_oam_features(pb)
    d880 = pb.memory[0xD880]
    ffbf = pb.memory[0xFFBF]
    ty = target_y if target_y is not None else TARGET_Y
    xt = x_tol if x_tol is not None else X_ALIGN_TOL
    # NOTE: action stochasticity removed — Sara's alignment is brittle and random
    # actions disrupt the kill. We still vary target_y/x_tol per episode for diversity.
    if d880 == 0x0a or ffbf != 0:
        return A_UP
    if sara_x < 0 or boss_x < 0:
        return A_UPA
    if sara_y > ty + 8:
        if abs(sara_x - boss_x) <= xt:
            return A_UPA
        return A_UP
    if sara_x < boss_x - xt:
        return A_RIGHT
    if sara_x > boss_x + xt:
        return A_LEFT
    return A_UPA


def rollout(env, ep_idx, fout, obs_buf, act_buf, kill_buf, src_buf, prev_dcbb_buf, rng):
    obs, info = env.reset()
    prev_dcbb = env.pb.memory[0xDCBB]
    prev_d880 = env.pb.memory[0xD880]
    init_ffba = env.pb.memory[0xFFBA]
    kill_event_in_ep = False
    ffba_advanced = False
    arena_to_post = False
    arena_to_death_low_hp = False
    step_records = []
    # Per-episode oracle perturbations
    target_y = int(rng.integers(70, 96))
    x_tol = int(rng.integers(4, 12))
    for step in range(MAX_EP_STEPS):
        a = oracle_action(env.pb, rng=rng, target_y=target_y, x_tol=x_tol)
        obs2, r, term, trunc, info = env.step(a)
        m = env.pb.memory
        cur_d880 = m[0xD880]
        cur_dcbb = m[0xDCBB]
        cur_ffba = m[0xFFBA]
        cur_ffbf = m[0xFFBF]
        kill_event = 0
        # In-arena DCBB drop to 0 (or arena-low → death scene) = Shalamar dead
        in_arena_prev = 0x0C <= prev_d880 <= 0x14
        in_arena_cur = 0x0C <= cur_d880 <= 0x14
        if in_arena_prev and prev_dcbb > 0 and prev_dcbb <= 10 and cur_d880 == 0x17:
            arena_to_death_low_hp = True
            kill_event = 1
            kill_event_in_ep = True
        if in_arena_cur and prev_dcbb > 0 and cur_dcbb == 0:
            kill_event = 1
            kill_event_in_ep = True
        if cur_ffba > init_ffba:
            ffba_advanced = True
        if cur_d880 == 0x16:
            arena_to_post = True
        step_records.append({
            "f": step, "action": a,
            "D880": cur_d880, "FFBA": cur_ffba, "DCBB": cur_dcbb, "FFBF": cur_ffbf,
            "src": "shalamar_oracle", "kill_event": kill_event,
        })
        obs_buf.append(obs.copy())
        act_buf.append(a)
        kill_buf.append(kill_event)
        src_buf.append("shalamar_oracle")
        prev_dcbb_buf.append(prev_dcbb)
        prev_dcbb = cur_dcbb
        prev_d880 = cur_d880
        obs = obs2
        if ffba_advanced or arena_to_post or arena_to_death_low_hp:
            break
        if term or trunc:
            break
    for rec in step_records:
        fout.write(json.dumps(rec) + "\n")
    print(f"  ep{ep_idx}: steps={step+1} final_D880=0x{env.pb.memory[0xD880]:02x} "
          f"final_FFBA={env.pb.memory[0xFFBA]} final_DCBB={env.pb.memory[0xDCBB]} "
          f"ffba_adv={ffba_advanced} arena_to_post={arena_to_post} "
          f"arena_to_death_low={arena_to_death_low_hp} kill_in_ep={kill_event_in_ep}", flush=True)
    return ffba_advanced or arena_to_post or arena_to_death_low_hp


def main():
    os.makedirs(os.path.dirname(OUT_NPZ), exist_ok=True)
    env = ShalamarEnv(ROM, max_steps=MAX_EP_STEPS, savestate_path=STATE)
    obs_buf, act_buf, kill_buf, src_buf, prev_dcbb_buf = [], [], [], [], []
    n_success = 0
    t0 = time.time()
    rng = np.random.default_rng(20260510)
    with open(OUT_JSONL, "w") as fout:
        for ep in range(EPISODES):
            ok = rollout(env, ep, fout, obs_buf, act_buf, kill_buf, src_buf, prev_dcbb_buf, rng)
            if ok:
                n_success += 1
    env.close()
    elapsed = time.time() - t0
    print(f"\n=== DONE in {elapsed:.1f}s ===")
    print(f"Shalamar clears: {n_success}/{EPISODES}")
    print(f"Captured frames: {len(obs_buf):,}, kill_event frames: {sum(kill_buf)}")
    if obs_buf:
        X = np.stack(obs_buf).astype(np.float32)
        y = np.asarray(act_buf, dtype=np.int64)
        kill_mask = np.asarray(kill_buf, dtype=np.int64)
        src = np.asarray(src_buf)
        np.savez_compressed(OUT_NPZ, X=X, y=y, kill_mask=kill_mask, src=src)
        print(f"Saved {OUT_NPZ}  X.shape={X.shape}")


if __name__ == "__main__":
    main()
