"""Test multiprocessing subprocess env without torch in main."""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import sys, time
import multiprocessing as mp
import numpy as np

sys.path.insert(0, "/home/struktured/projects/penta-dragon-dx-claude/rl")
from penta_rl.env_worker import env_worker


def main():
    cmd_q = mp.Queue()
    res_q = mp.Queue()
    worker = mp.Process(target=env_worker, args=(cmd_q, res_q))
    worker.start()
    print("worker started", flush=True)

    obs, _, _, info = res_q.get()
    print(f"got initial: FFBA={info['level']} D880={hex(info['scene'])}", flush=True)

    rng = np.random.default_rng(0)
    t0 = time.time()
    for t in range(2000):
        a = int(rng.integers(0, 12))
        cmd_q.put(a)
        obs, rew, done, info = res_q.get()
        if done:
            cmd_q.put("reset")
            obs, _, _, info = res_q.get()
        if t % 200 == 0:
            print(f"  t={t} ({time.time()-t0:.2f}s)", flush=True)
    print(f"DONE {time.time()-t0:.2f}s", flush=True)
    cmd_q.put("close")
    worker.join(timeout=5)


if __name__ == "__main__":
    mp.set_start_method("spawn")
    main()
