"""Verify BG colorization during gameplay.

Boots ROM, auto-presses start to enter gameplay, waits for settle, dumps BG
palette RAM + tile-attribute histogram. PASS if:
  - BG palette RAM has ≥3 distinct words (i.e. not all FF7F=white)
  - BG attr histogram uses ≥2 different palette indices (tiles routed to
    non-default palettes)

A FAIL means either CGB BG palette never got loaded (v290 white bug) or BG
tile attributes never got written (no colorization for tiles).
"""
from __future__ import annotations
import os, sys, subprocess, tempfile, argparse


def run_probe(rom_path: str, max_frames: int = 1200) -> dict:
    out = tempfile.NamedTemporaryFile(suffix=".txt", delete=False).name
    env = os.environ.copy()
    env["STATE_PATH"] = out
    env["MAX_FRAMES"] = str(max_frames)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["SDL_AUDIODRIVER"] = "dummy"
    cmd = ["xvfb-run", "-a", "mgba-qt", rom_path,
           "--script", "scripts/probes/gameplay_palette.lua", "-l", "0"]
    subprocess.run(cmd, env=env, capture_output=True, timeout=120)
    if not os.path.exists(out) or os.path.getsize(out) < 10:
        raise RuntimeError(f"gameplay_palette produced no output for {rom_path}")
    with open(out) as fh:
        text = fh.read()
    try: os.unlink(out)
    except OSError: pass
    return parse(text)


def parse(text: str) -> dict:
    pal_words = []
    attr_counts = {}
    state = {}
    for line in text.splitlines():
        if line.startswith("pal") and ":" in line:
            words = line.split(":", 1)[1].strip().split()
            pal_words.extend(words)
        elif line.startswith("attr_pal"):
            idx = int(line[len("attr_pal"):].split("=")[0])
            cnt = int(line.split("=")[1])
            attr_counts[idx] = cnt
        elif "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            state[k.strip()] = v.strip()
    return {"pal_words": pal_words, "attr_counts": attr_counts, "state": state}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--max-frames", type=int, default=1200)
    ap.add_argument("--min-distinct-pal-words", type=int, default=3,
                    help="PASS if BG palette RAM has at least this many distinct words")
    ap.add_argument("--min-attr-pal-indices", type=int, default=2,
                    help="PASS if BG attrs use at least this many distinct palette indices")
    args = ap.parse_args()

    r = run_probe(args.rom, args.max_frames)
    print(f"ROM: {args.rom}")
    print(f"State: {r['state']}")
    distinct_pal = len(set(r['pal_words']))
    print(f"BG palette RAM words: {len(r['pal_words'])} total, {distinct_pal} distinct")
    print(f"  words: {r['pal_words']}")
    nonzero_attr_indices = [i for i, c in r['attr_counts'].items() if c > 0]
    print(f"BG attr palette-index histogram: {r['attr_counts']}")
    print(f"  distinct palette indices in use: {len(nonzero_attr_indices)}")

    fail_reasons = []
    if r['state'].get('FFC1', '0') != '1':
        fail_reasons.append("never reached gameplay (FFC1 != 1)")
    if distinct_pal < args.min_distinct_pal_words:
        fail_reasons.append(f"only {distinct_pal} distinct palette words "
                            f"(need {args.min_distinct_pal_words}+) → BG palette load broken")
    if len(nonzero_attr_indices) < args.min_attr_pal_indices:
        fail_reasons.append(f"BG attrs use only {len(nonzero_attr_indices)} "
                            f"palette indices (need {args.min_attr_pal_indices}+) "
                            f"→ BG attribute write broken")

    if fail_reasons:
        print("\nFAIL:")
        for r in fail_reasons: print(f"  - {r}")
        sys.exit(1)
    else:
        print("\nPASS: BG colorization is active.")
        sys.exit(0)


if __name__ == "__main__":
    main()
