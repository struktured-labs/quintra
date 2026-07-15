"""Test 30 epochs of training but SKIP agent.update — see if hang persists."""
import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import sys, time
sys.path.insert(0, "/home/struktured/projects/penta-dragon-dx-claude/rl")
import torch
torch.set_num_threads(1)
from train_shalamar_np import ShalamarArenaEnv, boss_kill_reward_cfg, NumpyPolicy
from penta_rl.env import N_ACTIONS
from penta_rl.state import vector_dim
from penta_rl.ppo import PPOAgent, PPOConfig, TrajectoryBuffer
import numpy as np

ROM = "/home/struktured/projects/penta-dragon-dx-claude/rom/Penta Dragon (J) [A-fix].gb"
SHALAMAR = "/home/struktured/projects/penta-dragon-dx-claude/rl/saves/curriculum/arena_FFBA1_D880_0xd_FFD3_4.state"

device = "cpu"
env = ShalamarArenaEnv(ROM, max_steps=600, savestate_path=SHALAMAR,
                       reward_cfg=boss_kill_reward_cfg(), init_level=1)
obs_dim = vector_dim()
cfg = PPOConfig(epochs=30, steps_per_epoch=1024, train_iters=10, entropy_coef=0.03)
agent = PPOAgent(obs_dim, N_ACTIONS, cfg, device=device)
np_policy = NumpyPolicy(agent)

obs, info = env.reset()
init_ffba = info["state"].level
print(f"Start", flush=True)
t_start = time.time()
rng = np.random.default_rng(0)

for ep in range(30):
    t_ep = time.time()
    print(f"  EP {ep+1} START at t={time.time()-t_start:.1f}s", flush=True)
    n_done = 0
    for t in range(1024):
        logits, v = np_policy.forward(obs)
        probs = np.exp(logits - logits.max())
        probs /= probs.sum()
        a = int(rng.choice(N_ACTIONS, p=probs))
        obs2, rew, term, trunc, info2 = env.step(a)
        done = term or trunc
        if info2["state"].level > init_ffba:
            done = True
        if done:
            n_done += 1
            obs, info = env.reset()
        else:
            obs = obs2
    print(f"  EP {ep+1} DONE: {n_done} eps, {time.time()-t_ep:.2f}s", flush=True)
    # SKIP agent.update — just see if hang persists without it
print(f"Total: {time.time()-t_start:.1f}s", flush=True)
env.close()
