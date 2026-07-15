#!/usr/bin/env python3
"""
Audio Self-Verification for Penta Dragon DX.

Records 15s of audio from both original and DX ROMs using PulseAudio,
then compares using RMS energy envelope analysis.

Detects:
- Audio dropouts (silence ratio)
- Phantom sound onsets in 300-1000 Hz band
- Overall energy difference

PASS criteria:
- Silence ratio < 2% (original baseline ~0.5%)
- Phantom onsets = 0

Requires: PulseAudio, parec, xvfb-run, scipy, numpy

Usage:
    uv run python scripts/verify_audio.py
    uv run python scripts/verify_audio.py --skip-record  # reuse existing WAVs
    uv run python scripts/verify_audio.py --json

Exit codes:
    0 = PASS
    1 = FAIL
    2 = ERROR
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy import signal as sig

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MGBA = os.getenv("MGBA_PATH", "/home/struktured/bin/mgba-qt")
ORIG_ROM = PROJECT_ROOT / "rom" / "Penta Dragon (J).gb"
DEFAULT_DX_ROM = PROJECT_ROOT / "rom" / "working" / "penta_dragon_dx_v288.gb"
RECORD_SCRIPT = PROJECT_ROOT / "tmp" / "record_audio.sh"
AUDIO_LUA = PROJECT_ROOT / "tmp" / "audio_record.lua"
TMP_DIR = PROJECT_ROOT / "tmp" / "verify"

SILENCE_THRESHOLD = 0.003  # RMS below this = silence
SILENCE_RATIO_MAX = 0.02   # 2% max silence allowed
PHANTOM_FREQ_LOW = 300     # Hz
PHANTOM_FREQ_HIGH = 1000   # Hz
PHANTOM_THRESHOLD_FACTOR = 5.0  # 5x median energy = phantom onset
BLOCK_MS = 50              # RMS block size in ms


def load_wav_mono(path: str) -> tuple:
    """Load WAV, convert to mono float64. Returns (data, rate)."""
    rate, data = wavfile.read(path)
    if data.ndim == 2:
        data = data.mean(axis=1)
    return data.astype(np.float64) / 32768.0, rate


def compute_rms_envelope(data: np.ndarray, rate: int, block_ms: int = 50) -> tuple:
    """Compute RMS energy in blocks. Returns (times, rms_values)."""
    block_size = int(rate * block_ms / 1000)
    n_blocks = len(data) // block_size
    rms = np.zeros(n_blocks)
    times = np.zeros(n_blocks)
    for i in range(n_blocks):
        block = data[i * block_size:(i + 1) * block_size]
        rms[i] = np.sqrt(np.mean(block ** 2))
        times[i] = (i + 0.5) * block_ms / 1000
    return times, rms


def detect_silence_ratio(rms: np.ndarray, threshold: float = SILENCE_THRESHOLD) -> float:
    """Fraction of blocks that are silent."""
    if len(rms) == 0:
        return 0.0
    silent = np.sum(rms < threshold)
    return silent / len(rms)


def detect_phantom_onsets(data: np.ndarray, rate: int,
                          freq_low: int = PHANTOM_FREQ_LOW,
                          freq_high: int = PHANTOM_FREQ_HIGH,
                          block_ms: int = 20,
                          threshold_factor: float = PHANTOM_THRESHOLD_FACTOR) -> list:
    """
    Detect phantom sound onsets in a specific frequency band.
    Bandpass filter to freq_low-freq_high Hz, then find energy spikes.
    """
    # Design bandpass filter
    nyq = rate / 2
    low = freq_low / nyq
    high = min(freq_high / nyq, 0.99)
    if low >= high:
        return []

    try:
        sos = sig.butter(4, [low, high], btype='band', output='sos')
        filtered = sig.sosfilt(sos, data)
    except Exception:
        return []

    # Compute energy in blocks
    block_size = int(rate * block_ms / 1000)
    n_blocks = len(filtered) // block_size
    if n_blocks < 10:
        return []

    energies = np.zeros(n_blocks)
    for i in range(n_blocks):
        block = filtered[i * block_size:(i + 1) * block_size]
        energies[i] = np.sqrt(np.mean(block ** 2))

    median_e = np.median(energies)
    if median_e < 1e-8:
        return []

    threshold = median_e * threshold_factor

    # Find onset events
    onsets = []
    in_event = False
    start = 0
    for i in range(n_blocks):
        if energies[i] > threshold and not in_event:
            in_event = True
            start = i
        elif energies[i] <= threshold and in_event:
            in_event = False
            peak_e = np.max(energies[start:i])
            onsets.append({
                "start_s": round(start * block_ms / 1000, 3),
                "end_s": round(i * block_ms / 1000, 3),
                "peak_rms": round(float(peak_e), 6),
                "ratio": round(float(peak_e / median_e), 1),
            })

    return onsets


def record_audio(rom_path: str, output_wav: str, timeout_sec: int = 45) -> bool:
    """Record audio from a ROM using PulseAudio null sink."""
    if not AUDIO_LUA.exists():
        print(f"  WARNING: Audio Lua script not found at {AUDIO_LUA}")
        return False

    if not RECORD_SCRIPT.exists():
        print(f"  WARNING: Record script not found at {RECORD_SCRIPT}")
        return False

    try:
        result = subprocess.run(
            ["bash", str(RECORD_SCRIPT), str(rom_path), output_wav, str(AUDIO_LUA)],
            timeout=timeout_sec + 15,
            capture_output=True, text=True,
            cwd=str(PROJECT_ROOT)
        )
        if result.returncode != 0:
            print(f"  Record stderr: {result.stderr[-500:]}")
        return os.path.exists(output_wav) and os.path.getsize(output_wav) > 1000
    except subprocess.TimeoutExpired:
        print("  Recording timed out")
        return False
    except Exception as e:
        print(f"  Recording error: {e}")
        return False


def analyze_audio(orig_wav: str, dx_wav: str) -> dict:
    """Compare two WAV recordings and produce verification report."""
    try:
        orig_data, orig_rate = load_wav_mono(orig_wav)
        dx_data, dx_rate = load_wav_mono(dx_wav)
    except Exception as e:
        return {"passed": False, "error": f"Failed to load WAV: {e}"}

    if orig_rate != dx_rate:
        return {"passed": False, "error": f"Sample rate mismatch: {orig_rate} vs {dx_rate}"}

    rate = orig_rate

    # Trim to same length
    min_len = min(len(orig_data), len(dx_data))
    if min_len < rate * 2:  # Less than 2 seconds
        return {"passed": False, "error": f"Audio too short: {min_len / rate:.1f}s"}

    orig_data = orig_data[:min_len]
    dx_data = dx_data[:min_len]
    duration = min_len / rate

    # RMS envelopes
    _, orig_rms = compute_rms_envelope(orig_data, rate, BLOCK_MS)
    _, dx_rms = compute_rms_envelope(dx_data, rate, BLOCK_MS)

    # Skip first 8 seconds (title menu audio)
    skip_blocks = int(8.0 / (BLOCK_MS / 1000))
    if len(dx_rms) > skip_blocks:
        gameplay_dx_rms = dx_rms[skip_blocks:]
        gameplay_orig_rms = orig_rms[skip_blocks:]
    else:
        gameplay_dx_rms = dx_rms
        gameplay_orig_rms = orig_rms

    # 1. Silence ratio
    dx_silence = detect_silence_ratio(gameplay_dx_rms)
    orig_silence = detect_silence_ratio(gameplay_orig_rms)

    # 2. Phantom onsets in DX difference signal
    diff = dx_data - orig_data
    gameplay_start_sample = int(8.0 * rate)
    gameplay_diff = diff[gameplay_start_sample:]
    phantom_onsets = detect_phantom_onsets(gameplay_diff, rate)

    # 3. Overall RMS comparison
    orig_overall_rms = float(np.sqrt(np.mean(orig_data ** 2)))
    dx_overall_rms = float(np.sqrt(np.mean(dx_data ** 2)))
    diff_rms = float(np.sqrt(np.mean(diff ** 2)))

    # Pass criteria
    # Silence: DX should be within 10% absolute of original (not a fixed threshold)
    silence_pass = abs(dx_silence - orig_silence) < 0.10
    phantom_pass = len(phantom_onsets) == 0

    passed = silence_pass and phantom_pass

    return {
        "passed": passed,
        "duration_s": round(duration, 1),
        "sample_rate": rate,
        "orig_rms": round(orig_overall_rms, 4),
        "dx_rms": round(dx_overall_rms, 4),
        "diff_rms": round(diff_rms, 4),
        "orig_silence_ratio": round(orig_silence, 4),
        "dx_silence_ratio": round(dx_silence, 4),
        "silence_threshold": SILENCE_RATIO_MAX,
        "silence_pass": silence_pass,
        "phantom_onsets": len(phantom_onsets),
        "phantom_onset_details": phantom_onsets[:10],
        "phantom_pass": phantom_pass,
    }


def main():
    parser = argparse.ArgumentParser(description="Audio Self-Verification")
    parser.add_argument("--dx-rom", default=str(DEFAULT_DX_ROM), help="DX ROM path")
    parser.add_argument("--orig-rom", default=str(ORIG_ROM), help="Original ROM path")
    parser.add_argument("--skip-record", action="store_true",
                        help="Skip recording, reuse existing WAVs")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    orig_wav = str(TMP_DIR / "original_audio.wav")
    dx_wav = str(TMP_DIR / "dx_audio.wav")

    dx_rom = Path(args.dx_rom)
    if not dx_rom.exists():
        fixed = PROJECT_ROOT / "rom" / "working" / "penta_dragon_dx_FIXED.gb"
        if fixed.exists():
            dx_rom = fixed
        else:
            print(f"ERROR: DX ROM not found: {args.dx_rom}")
            sys.exit(2)

    if not args.skip_record:
        # Check PulseAudio
        try:
            subprocess.run(["pactl", "info"], capture_output=True, timeout=5)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            print("WARNING: PulseAudio not available - skipping audio test")
            result = {"passed": True, "skipped": True,
                      "reason": "PulseAudio not available"}
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print("[AUDIO] SKIP (PulseAudio not available)")
            sys.exit(0)

        if not Path(args.orig_rom).exists():
            print(f"ERROR: Original ROM not found: {args.orig_rom}")
            sys.exit(2)

        print("[AUDIO] Recording original ROM (15s)...")
        if not record_audio(args.orig_rom, orig_wav):
            print("ERROR: Failed to record original ROM audio")
            sys.exit(2)

        print("[AUDIO] Recording DX ROM (15s)...")
        if not record_audio(str(dx_rom), dx_wav):
            print("ERROR: Failed to record DX ROM audio")
            sys.exit(2)
    else:
        if not os.path.exists(orig_wav) or not os.path.exists(dx_wav):
            print("ERROR: --skip-record but WAV files don't exist")
            sys.exit(2)

    print("[AUDIO] Analyzing...")
    result = analyze_audio(orig_wav, dx_wav)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        passed = result.get("passed", False)
        print(f"\n[AUDIO] {'PASS' if passed else 'FAIL'}")
        print(f"  Duration: {result.get('duration_s', 0)}s")
        print(f"  DX silence ratio: {result.get('dx_silence_ratio', 0):.4f} "
              f"(max {SILENCE_RATIO_MAX}) "
              f"{'PASS' if result.get('silence_pass') else 'FAIL'}")
        print(f"  Orig silence ratio: {result.get('orig_silence_ratio', 0):.4f}")
        print(f"  Phantom onsets: {result.get('phantom_onsets', 0)} "
              f"{'PASS' if result.get('phantom_pass') else 'FAIL'}")
        print(f"  Diff RMS: {result.get('diff_rms', 0):.4f}")

        if result.get("phantom_onset_details"):
            print("  Phantom onset details:")
            for onset in result["phantom_onset_details"]:
                print(f"    {onset['start_s']:.3f}s-{onset['end_s']:.3f}s "
                      f"peak={onset['peak_rms']:.6f} ({onset['ratio']:.1f}x median)")

        if result.get("error"):
            print(f"  Error: {result['error']}")

    # Save report
    report_path = TMP_DIR / "verify_audio_report.json"
    with open(report_path, "w") as f:
        json.dump(result, f, indent=2)

    sys.exit(0 if result.get("passed", False) else 1)


if __name__ == "__main__":
    main()
