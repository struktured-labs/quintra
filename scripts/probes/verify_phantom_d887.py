"""Phantom-sound verification.

Runs phantom_d887.lua against ROM, then compares D887 transition count to the
vanilla baseline. Vanilla coalesces D887 writes via the original game's sound
engine; modded builds with bank-switch bugs (FF99 / trampoline / VBlank
overrun) lose coalescence, producing many more transitions.

Usage:
    python verify_phantom_d887.py <rom> [--baseline-rom <vanilla>]
                                        [--frames N] [--tolerance 1.5]

Exit 0 = PASS (transitions <= tolerance × baseline)
Exit 1 = FAIL (more transitions than allowed)
Exit 2 = harness error
"""
from __future__ import annotations
import os, sys, subprocess, tempfile, argparse


def run_d887(rom_path: str, frames: int) -> dict:
    out = tempfile.NamedTemporaryFile(suffix=".txt", delete=False).name
    env = os.environ.copy()
    env["STATE_PATH"] = out
    env["MEASURE_FRAMES"] = str(frames)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["SDL_AUDIODRIVER"] = "dummy"
    cmd = ["xvfb-run", "-a", "mgba-qt", rom_path,
           "--script", "scripts/probes/phantom_d887.lua", "-l", "0"]
    subprocess.run(cmd, env=env, capture_output=True, timeout=180)
    if not os.path.exists(out) or os.path.getsize(out) < 10:
        raise RuntimeError(f"phantom_d887 produced no output for {rom_path}")
    with open(out) as fh:
        text = fh.read()
    transitions = None
    for line in text.splitlines():
        if line.startswith("transitions="):
            transitions = int(line.split("=")[1])
            break
    try: os.unlink(out)
    except OSError: pass
    if transitions is None:
        raise RuntimeError(f"could not parse transitions from {out}")
    return {"transitions": transitions, "raw": text}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--baseline-rom",
                    default="rom/Penta Dragon (J).gb",
                    help="Vanilla ROM for D887 baseline (default: vanilla)")
    ap.add_argument("--frames", type=int, default=600,
                    help="Total frames to monitor (default 600 ≈ 10s)")
    ap.add_argument("--tolerance", type=float, default=1.5,
                    help="PASS if rom transitions <= tolerance × baseline (default 1.5)")
    args = ap.parse_args()

    print(f"Measuring {args.baseline_rom} (baseline)...")
    baseline = run_d887(args.baseline_rom, args.frames)
    print(f"  baseline: {baseline['transitions']} D887 transitions")

    print(f"Measuring {args.rom}...")
    candidate = run_d887(args.rom, args.frames)
    print(f"  candidate: {candidate['transitions']} D887 transitions")

    threshold = max(int(baseline['transitions'] * args.tolerance), 5)
    print(f"\nThreshold: {threshold} (= {args.tolerance} × baseline, min 5)")

    if candidate['transitions'] > threshold:
        print(f"\nFAIL: candidate {candidate['transitions']} > threshold {threshold}\n"
              f"      Extra D887 churn suggests phantom-sound regression "
              f"(+{candidate['transitions']-baseline['transitions']} vs baseline).")
        sys.exit(1)
    else:
        print(f"\nPASS: candidate {candidate['transitions']} ≤ threshold {threshold} "
              f"(baseline-equivalent D887 behavior).")
        sys.exit(0)


if __name__ == "__main__":
    main()
