"""Standalone env worker for multiprocessing — does NOT import torch.

Receives action ints from cmd_q. Sends (obs, rew, done, info_dict) via res_q.
Special commands: "reset", "close".
"""
import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import sys
sys.path.insert(0, "/home/struktured/projects/penta-dragon-dx-claude/rl")

ROM = "/home/struktured/projects/penta-dragon-dx-claude/rom/Penta Dragon (J) [A-fix].gb"
SHALAMAR = "/home/struktured/projects/penta-dragon-dx-claude/rl/saves/curriculum/arena_FFBA1_D880_0xd_FFD3_4.state"


def env_worker(cmd_q, res_q, savestate_path=SHALAMAR, init_level=1):
    """Lightweight env worker — only PyBoy + numpy, no torch."""
    # Import inside function so child process imports happen fresh
    from pyboy import PyBoy
    from penta_rl.state import read_state, state_to_vector
    from penta_rl.reward import RewardConfig, RewardTracker
    from penta_rl.env import ACTION_BUTTONS
    from penta_rl.godmode_env import godmode_step

    pb = PyBoy(ROM, window="null", sound_emulated=False, cgb=True)
    cfg = RewardConfig()
    cfg.step_penalty = -0.005
    cfg.boss_damage = 0.5
    cfg.boss_kill = 200.0
    cfg.boss_kill_chain = 50.0
    cfg.unique_room = 5.0
    tracker = RewardTracker(cfg)

    def reset():
        with open(savestate_path, "rb") as fh:
            pb.load_state(fh)
        tracker.reset()
        s = read_state(pb)
        tracker.last_state = s
        return state_to_vector(s), s

    obs, s = reset()
    held = []
    steps = 0
    max_steps = 600

    res_q.put((obs, 0.0, False, {"level": s.level, "scene": s.scene, "player_hp": s.player_hp}))
    while True:
        cmd = cmd_q.get()
        if cmd == "close":
            pb.stop()
            return
        elif cmd == "reset":
            obs, s = reset()
            held = []
            steps = 0
            res_q.put((obs, 0.0, False, {"level": s.level, "scene": s.scene, "player_hp": s.player_hp}))
        else:
            a = int(cmd)
            for b in held:
                pb.button_release(b)
            held = ACTION_BUTTONS[a]
            for b in held:
                pb.button_press(b)
            for _ in range(4):  # frame_skip=4
                godmode_step(pb)
                pb.tick()
            steps += 1
            s = read_state(pb)
            reward, info = tracker.step(s, action=a)
            success = s.level > init_level
            terminated = success
            truncated = steps >= max_steps
            done = terminated or truncated
            if success:
                reward += 500.0
            res_q.put((state_to_vector(s), float(reward), done,
                       {"level": s.level, "scene": s.scene, "player_hp": s.player_hp}))
