"""Curriculum PPO from converted user demo states.

Each episode randomly samples a starting state from rl/saves/user_demo/converted/.
Reward signal mirrors train_explore_natural.py (section bonus, kill bonus, FFBA advance).

States span: early L1 → SHMUP → Boss arena → L2. Training from ANY of them gives
gradient signal on the corresponding game segment, accelerating beyond the
gameplay_start-only exploration plateau.
"""
from __future__ import annotations
import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import json, sys, time, glob, random
import numpy as np
import torch
torch.set_num_threads(1)

sys.path.insert(0, "/home/struktured/projects/penta-dragon-dx-claude/rl")
from penta_rl.env import N_ACTIONS, PentaEnv, ACTION_BUTTONS
from penta_rl.godmode_env import godmode_step
from penta_rl.state import vector_dim, read_state, state_to_vector
from penta_rl.ppo import PPOAgent, PPOConfig, TrajectoryBuffer
from penta_rl.reward import RewardConfig
from train_shalamar_np import NumpyPolicy
from train_explore_natural import explore_reward_cfg

ROM = "/home/struktured/projects/penta-dragon-dx-claude/rom/Penta Dragon (J) [A-fix].gb"
CONVERTED_DIR = "/home/struktured/projects/penta-dragon-dx-claude/rl/saves/user_demo/converted"
ARENA_DIR = "/home/struktured/projects/penta-dragon-dx-claude/rl/saves/curriculum"
GAMEPLAY = "/home/struktured/projects/penta-dragon-dx-claude/rl/saves/gameplay_start.state"
V19_CKPT = "/home/struktured/projects/penta-dragon-dx-claude/rl/ppo_v19_resume18_ep200.pt"
NATURAL_LATEST = "/home/struktured/projects/penta-dragon-dx-claude/rl/ppo_explore_natural_latest.pt"
OUT_DIR = "/home/struktured/projects/penta-dragon-dx-claude/rl"

# Scenes known to be policy-traps where PyBoy can hang or game logic stalls.
# Per project memory: D880=0x0b is a stuck state surfaced during stage-boss work.
STUCK_SCENES = {0x0b}
STUCK_TICK_LIMIT = 240          # ~16s at 4-frame skip — terminate sooner than max_steps
STALE_POS_LIMIT = 480           # truncate if Sara hasn't moved for ~32s


class DemoCurriculumEnv(PentaEnv):
    """Sample a different demo state each reset."""

    def __init__(self, *args, demo_states=None, arena_states=None,
                 gameplay_weight=0.2, **kwargs):
        # Use first demo state as default to satisfy parent
        self.demo_states = list(demo_states or [])
        self.arena_states = list(arena_states or [])
        self.gameplay_weight = gameplay_weight
        # Pre-classify demo states by FFBA value (read meta-style by file name).
        # FFBA=1 states (L2 starts) are the ONLY path to FFBA=2 advance. Weight heavily.
        ffba1_names = {"195759_L2_pumpkin_mb", "200043_L2_seahorse_mb",
                       "200142_L2_post_troll_tp", "CHECKPOINT_200320"}
        self.l2_states = [s for s in self.demo_states
                          if os.path.basename(s).replace(".state", "") in ffba1_names]
        self.l1_states = [s for s in self.demo_states if s not in self.l2_states]
        # Bootstrap with gameplay_start (first reset uses it; later resets sample)
        super().__init__(*args, savestate_path=GAMEPLAY, **kwargs)
        self._visited = set()
        self._init_ffba = 0
        self._max_dcb8 = 0
        self._cur_state_path = GAMEPLAY
        self._stuck_scene_count = 0

    def _pick_state(self):
        if not self.demo_states:
            return GAMEPLAY
        # 35% L2 (FFBA=1, path to FFBA=2 advance)
        # 25% L1 demo (varied rooms in level 1)
        # 25% arena (FFBA=1..8 stage-boss arenas — direct boss-fight curriculum)
        # 15% gameplay_start (natural-explore baseline)
        r = random.random()
        if r < 0.35 and self.l2_states:
            return random.choice(self.l2_states)
        elif r < 0.60 and self.l1_states:
            return random.choice(self.l1_states)
        elif r < 0.85 and self.arena_states:
            return random.choice(self.arena_states)
        else:
            return GAMEPLAY

    def reset(self, seed=None, options=None):
        self._visited = set()
        self._max_dcb8 = 0
        self._stale_count = 0
        self._last_pos = None
        self._stuck_scene_count = 0
        # Choose a state for this episode
        self._cur_state_path = self._pick_state()
        self.savestate_path = self._cur_state_path
        if self.pb is None:
            obs, info = super().reset(seed=seed, options=options)
            self._init_ffba = info["state"].level
            self._max_dcb8 = self.pb.memory[0xDCB8]
            info["src"] = os.path.basename(self._cur_state_path)
            return obs, info
        with open(self.savestate_path, "rb") as fh:
            self.pb.load_state(fh)
        self.reward_tracker.reset()
        self.steps = 0
        self._held = []
        s = read_state(self.pb)
        self.reward_tracker.last_state = s
        self._init_ffba = s.level
        self._max_dcb8 = self.pb.memory[0xDCB8]
        return state_to_vector(s), {"state": s, "src": os.path.basename(self._cur_state_path)}

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
        cur_dcb8 = self.pb.memory[0xDCB8]
        key = (s.level, s.room, cur_dcb8)
        if key not in self._visited:
            self._visited.add(key)
            reward += 10.0
        if cur_dcb8 > self._max_dcb8 and cur_dcb8 < 0x80:
            advance = cur_dcb8 - self._max_dcb8
            reward += 50.0 * advance
            self._max_dcb8 = cur_dcb8
        py = self.pb.memory[0xFE05]
        px = self.pb.memory[0xFE04]
        cur_pos = (s.room, py // 8, px // 8)
        # Stop stagnation penalty if Sara is dead (scene 0x17) — body locks
        # and accumulates -100+ penalty over rest of episode unfairly.
        if cur_pos == self._last_pos and s.scene != 0x17:
            self._stale_count += 1
            if self._stale_count > 60:
                reward -= 0.1
        else:
            self._stale_count = 0
            if s.scene != 0x17:
                reward += 0.05
            self._last_pos = cur_pos
        if s.scene in STUCK_SCENES:
            self._stuck_scene_count += 1
        else:
            self._stuck_scene_count = 0
        # Stage boss arena entry
        if 0x0C <= s.scene <= 0x14:
            reward += 1.0  # tiny stay-in-arena bonus
        # FFBA advance from this episode's init.
        # Only count advances when starting from a "normal" level (0-7).
        # SHMUP states (init_ffba=7) can transition back to 0 — not progress.
        success = self._init_ffba < s.level <= 8 and self._init_ffba < 7
        terminated = success
        truncated = self.steps >= self.max_steps
        if success:
            info["success"] = True
            reward += 1000.0
        elif s.level > 8:
            # FFBA corruption — silently terminate, no penalty (dragged returns down)
            terminated = True
        # Terminate on death scene so we don't waste frames stuck in 0x17
        if s.scene == 0x17 and not terminated and not truncated:
            truncated = True
        # Truncate stuck-state episodes early so they don't burn the chunk timeout
        if not terminated and not truncated:
            if self._stuck_scene_count >= STUCK_TICK_LIMIT:
                truncated = True
                info["stuck_scene"] = hex(s.scene)
            elif self._stale_count >= STALE_POS_LIMIT:
                truncated = True
                info["stale_pos"] = True
        info["state"] = s
        info["steps"] = self.steps
        info["n_visited"] = len(self._visited)
        info["src"] = os.path.basename(self._cur_state_path)
        return state_to_vector(s), reward, terminated, truncated, info


def run_chunk(epochs, steps_per_epoch, label, resume_path=None):
    device = "cpu"
    demo_states = sorted(glob.glob(f"{CONVERTED_DIR}/*.state"))
    arena_states = sorted(glob.glob(f"{ARENA_DIR}/arena_FFBA*.state"))
    print(f"Loaded {len(demo_states)} demo states from {CONVERTED_DIR}", flush=True)
    print(f"Loaded {len(arena_states)} arena states from {ARENA_DIR}", flush=True)
    env = DemoCurriculumEnv(ROM, max_steps=1024, demo_states=demo_states,
                            arena_states=arena_states,
                            gameplay_weight=0.2, reward_cfg=explore_reward_cfg())
    obs_dim = vector_dim()
    cfg = PPOConfig(epochs=epochs, steps_per_epoch=steps_per_epoch,
                    train_iters=10, entropy_coef=0.05)
    agent = PPOAgent(obs_dim, N_ACTIONS, cfg, device=device)

    loaded = False
    if resume_path and os.path.exists(resume_path):
        state = torch.load(resume_path, map_location=device, weights_only=False)
        agent.net.load_state_dict(state["model"])
        prior_metrics = state.get("metrics", [])
        print(f"Resumed from {resume_path}, {len(prior_metrics)} prior epochs", flush=True)
        loaded = True
    elif os.path.exists(NATURAL_LATEST):
        # Bootstrap from natural-explore checkpoint
        state = torch.load(NATURAL_LATEST, map_location=device, weights_only=False)
        agent.net.load_state_dict(state["model"])
        prior_metrics = []
        print(f"Bootstrapped from natural-explore latest", flush=True)
        loaded = True
    if not loaded:
        prior_metrics = []

    np_policy = NumpyPolicy(agent)
    obs, info = env.reset()
    print(f"  start: src={info['src']} D880=0x{info['state'].scene:02x} "
          f"FFBA={info['state'].level} FFBD={info['state'].room} "
          f"FFBF={info['state'].miniboss}", flush=True)

    completed_returns = []
    src_kills = {}
    src_advances = {}
    src_visits = {}
    metrics = list(prior_metrics)
    t_start = time.time()
    rng = np.random.default_rng(int(time.time()) & 0xFFFF)

    def save_ckpt():
        save_path = f"{OUT_DIR}/ppo_{label}_chunk{len(metrics)}.pt"
        torch.save({"model": agent.net.state_dict(), "metrics": metrics,
                    "src_kills": src_kills, "src_advances": src_advances}, save_path)
        latest = f"{OUT_DIR}/ppo_{label}_latest.pt"
        if os.path.lexists(latest):
            os.unlink(latest)
        os.symlink(save_path, latest)

    for ep in range(epochs):
        buf = TrajectoryBuffer(obs_dim, steps_per_epoch)
        n_done = 0
        ep_reward = 0.0
        ep_src = info.get("src", "?")
        np_policy.refresh()
        for t in range(steps_per_epoch):
            logits, v = np_policy.forward(obs)
            probs = np.exp(logits - logits.max())
            probs /= probs.sum()
            a = int(rng.choice(N_ACTIONS, p=probs))
            lp = float(np.log(probs[a] + 1e-10))
            obs2, rew, term, trunc, info2 = env.step(a)
            done = term or trunc
            buf.store(obs, a, float(rew), v, lp, done)
            ep_reward += float(rew)
            if done:
                n_done += 1
                completed_returns.append(ep_reward)
                src_visits[ep_src] = src_visits.get(ep_src, 0) + 1
                if info2.get("success"):
                    src_advances[ep_src] = src_advances.get(ep_src, 0) + 1
                    print(f"  *** FFBA ADVANCE *** src={ep_src} reward={ep_reward:.2f}", flush=True)
                ep_reward = 0.0
                obs, info = env.reset()
                ep_src = info.get("src", "?")
            else:
                obs = obs2

        _, last_val = np_policy.forward(obs)
        data = buf.finish(cfg.gamma, cfg.lam, last_val=last_val)
        losses = agent.update(data)

        recent = completed_returns[-10:] or [0.0]
        elapsed = time.time() - t_start
        m = {
            "epoch": len(metrics) + 1, "elapsed_s": round(elapsed, 1),
            "n_eps_chunk": n_done,
            "mean_return": round(float(np.mean(recent)), 2),
            "max_return": round(float(max(recent)), 2),
            "src_visits": dict(src_visits),
            "src_advances": dict(src_advances),
            "loss_pi": round(losses["pi"], 4),
            "loss_v": round(losses["v"], 4),
            "entropy": round(losses["ent"], 4),
        }
        metrics.append(m)
        adv_total = sum(src_advances.values())
        print(f"ep {len(metrics):4d}  eps={n_done:2d}  ret={m['mean_return']:7.2f}  "
              f"max={m['max_return']:7.2f}  adv_total={adv_total}  "
              f"ent={m['entropy']:.3f}  t={elapsed:.0f}s", flush=True)
        save_ckpt()

    print(f"\nChunk done: {len(metrics)} epochs, {sum(src_advances.values())} total advances", flush=True)
    if src_advances:
        print(f"Per-src advances: {src_advances}", flush=True)
    env.close()


if __name__ == "__main__":
    epochs = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 1024
    label = sys.argv[3] if len(sys.argv) > 3 else "demo_curriculum"
    resume = sys.argv[4] if len(sys.argv) > 4 else f"{OUT_DIR}/ppo_{label}_latest.pt"
    run_chunk(epochs, steps, label, resume_path=resume)
