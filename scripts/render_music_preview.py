#!/usr/bin/env python3
"""Render cartridge-authentic Quintra soundtrack previews or complete forms.

Each file joins a full-density opening excerpt to a later development excerpt.
With ``--full-form``, each file instead runs from the first A-H form row through
the exact next loop boundary, exposing every transition and the final cadence.
The ROM itself selects and mixes the track; this script records PyBoy's actual
48 kHz output rather than synthesizing the C tables on the host. Boss previews
retain the live encounter mix while keeping the champion invulnerable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import test_music as music_test  # noqa: E402

STAGES = (
    "Crystal Caverns", "Verdant Hollow", "Ember Depths", "Frost Vault",
    "Toxic Mire", "Shadow Keep", "Golden Temple", "Bloodmoon",
    "Void Sanctum",
)
BOSSES = (
    "Crystal Colossus", "Briar Crown", "Cinder Maw", "Frost Wyrm",
    "Mire Sovereign", "Shadow Reaper", "Sun Golem", "Blood Hydra",
    "Void Lord",
)
SAMPLE_RATE = 48_000


def slug(text: str) -> str:
    return "-".join(text.lower().split())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def tick_mix(pb, track: int) -> np.ndarray | None:
    """Advance one hardware frame while keeping a live boss mix recordable."""
    pb.memory[music_test.PL + 1] = max(pb.memory[music_test.PL + 1], 40)
    pb.memory[music_test.PL + 2] = pb.memory[music_test.PL + 1]
    pb.memory[music_test.PL + 15] = 255
    pb.tick()
    if pb.memory[music_test.MUSIC] != track:
        raise RuntimeError(
            f"track {track} changed to {pb.memory[music_test.MUSIC]} while rendering"
        )
    frame = pb.sound.ndarray
    return frame.copy() if frame.size else None


def capture(pb, track: int, form_step: int, seconds: float) -> np.ndarray:
    pb.memory[music_test.MUSIC_FORM_STEP] = form_step
    pb.memory[music_test.MUSIC_PATTERN_ROW] = 0
    pb.memory[music_test.MUSIC_ROW] = 0
    chunks = []
    for _ in range(round(seconds * 60)):
        frame = tick_mix(pb, track)
        if frame is not None:
            chunks.append(frame)
    if not chunks:
        raise RuntimeError(f"track {track} produced no PCM")
    return np.concatenate(chunks, axis=0)


def capture_full_form(pb, track: int) -> np.ndarray:
    """Capture exactly one 32-section form between consecutive row-zero attacks."""
    # Synthetic route injection returns as soon as the destination room ID
    # changes; a large boss room may still be finishing its one-time setup.
    # Let that work and any accumulated VBlank delta drain before placing the
    # sequencer at A1, or the first audio update can legitimately consume two
    # score rows in one hardware frame.
    for _ in range(60):
        tick_mix(pb, track)
    pb.memory[music_test.MUSIC_FORM_STEP] = 0
    pb.memory[music_test.MUSIC_PATTERN_ROW] = 0
    pb.memory[music_test.MUSIC_ROW] = 0

    # The internal frame divider is intentionally private cartridge state.
    # Discard at most one partial row, then begin on the frame that actually
    # triggers section 0 / row 0 (telemetry advances to row 1 immediately).
    chunks = []
    for _ in range(120):
        frame = tick_mix(pb, track)
        if (pb.memory[music_test.MUSIC_FORM_STEP] == 0 and
                pb.memory[music_test.MUSIC_PATTERN_ROW] == 1):
            if frame is not None:
                chunks.append(frame)
            break
    else:
        raise RuntimeError(f"track {track} never synchronized to its first form row")

    saw_final_quarter = False
    for _ in range(60 * 100):
        frame = tick_mix(pb, track)
        step = pb.memory[music_test.MUSIC_FORM_STEP]
        row = pb.memory[music_test.MUSIC_PATTERN_ROW]
        if step >= 24:
            saw_final_quarter = True
        if saw_final_quarter and step == 0 and row == 1:
            break
        if frame is not None:
            chunks.append(frame)
    else:
        raise RuntimeError(f"track {track} did not wrap its complete form within 100s")
    if not chunks:
        raise RuntimeError(f"track {track} produced no full-form PCM")
    return np.concatenate(chunks, axis=0)


def write_wave(path: Path, pcm8: np.ndarray) -> None:
    pcm16 = (pcm8.astype(np.int16) << 8).astype("<i2", copy=False)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(pcm16.tobytes())


def cue_timestamp(samples: int) -> str:
    cue_frames = round(samples * 75 / SAMPLE_RATE)
    minutes, remainder = divmod(cue_frames, 75 * 60)
    seconds, frames = divmod(remainder, 75)
    return f"{minutes:02d}:{seconds:02d}:{frames:02d}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "tmp/music-preview")
    parser.add_argument("--seconds", type=float, default=8.0,
                        help="seconds per opening/development excerpt")
    parser.add_argument("--full-form", action="store_true",
                        help="capture each complete 32-section form instead of excerpts")
    parser.add_argument("--stage", type=int, action="append",
                        help="stage number 1..9; repeatable (default: all)")
    parser.add_argument("--stage-only", action="store_true")
    parser.add_argument("--boss-only", action="store_true")
    args = parser.parse_args()
    if args.stage_only and args.boss_only:
        parser.error("--stage-only and --boss-only are mutually exclusive")
    stages = args.stage or list(range(1, 10))
    if any(stage < 1 or stage > 9 for stage in stages):
        parser.error("--stage must be 1..9")
    if not 1 <= args.seconds <= 30:
        parser.error("--seconds must be 1..30")

    args.out.mkdir(parents=True, exist_ok=True)
    for stale in args.out.glob("*.wav"):
        stale.unlink()
    records = []
    album_chunks = []
    prefix = "music-full" if args.full_form else "music-preview"
    for stage_number in stages:
        stage = stage_number - 1
        kinds = (False, True)
        if args.stage_only:
            kinds = (False,)
        elif args.boss_only:
            kinds = (True,)
        for boss in kinds:
            pb, track = music_test.runtime_track(stage, boss, keep_emulator=True)
            try:
                if args.full_form:
                    pcm = capture_full_form(pb, track)
                else:
                    opening = capture(pb, track, 2, args.seconds)
                    development = capture(pb, track, 17, args.seconds)
                    gap = np.zeros((SAMPLE_RATE // 2, 2), dtype=np.int8)
                    pcm = np.concatenate((opening, gap, development), axis=0)
            finally:
                pb.stop(save=False)
            album_chunks.append(pcm)
            label = BOSSES[stage] if boss else STAGES[stage]
            kind = "boss" if boss else "stage"
            order = "b-boss" if boss else "a-stage"
            path = args.out / f"{stage_number:02d}-{order}-{slug(label)}.wav"
            write_wave(path, pcm)
            rms = float(np.sqrt(np.mean(pcm.astype(np.float64) ** 2)))
            silence = float(np.mean(np.all(pcm == 0, axis=1)))
            peak = int(np.max(np.abs(pcm.astype(np.int16))))
            if peak >= 127:
                raise RuntimeError(f"{label} clips the signed 8-bit cartridge mix")
            if rms < 1.0 or silence > 0.5:
                raise RuntimeError(
                    f"{label} produced an inaudible preview: rms={rms:.2f}, silence={silence:.1%}"
                )
            record = {
                "stage": stage_number,
                "kind": kind,
                "name": label,
                "track_id": track,
                "seconds": round(len(pcm) / SAMPLE_RATE, 3),
                "peak_int8": peak,
                "rms_int8": round(rms, 3),
                "silence_ratio": round(silence, 4),
                "file": path.name,
                "sha256": sha256(path),
            }
            if args.full_form:
                tempo = music_test.table_tempos(
                    "boss_music" if boss else "stage_music"
                )[stage]
                nominal_seconds = tempo * 512 / 60
                drift_seconds = record["seconds"] - nominal_seconds
                drift_ratio = drift_seconds / nominal_seconds
                # Live Colossus captures deliberately retain combat and SFX.
                # A busy video frame may defer one game-loop music tick, so
                # report real encounter drift and reject only an audible tempo
                # collapse. Exploration captures also retain their generated
                # encounter, so the same upper bound applies to both routes.
                allowed_drift = 0.005
                if abs(drift_ratio) > allowed_drift:
                    raise RuntimeError(
                        f"{label} full form is {record['seconds']:.3f}s; "
                        f"expected {nominal_seconds:.3f}s "
                        f"({drift_ratio:+.1%} live-tempo drift)"
                    )
                bounds = np.linspace(0, len(pcm), 33, dtype=int)
                section_rms = [
                    float(np.sqrt(np.mean(
                        pcm[bounds[index]:bounds[index + 1]].astype(np.float64) ** 2
                    )))
                    for index in range(32)
                ]
                section_hashes = {
                    hashlib.sha256(
                        pcm[bounds[index]:bounds[index + 1]].tobytes()
                    ).digest()
                    for index in range(32)
                }
                section_rms_span = max(section_rms) - min(section_rms)
                if section_rms_span < 4.0:
                    raise RuntimeError(
                        f"{label} lacks whole-form dynamic development: "
                        f"section RMS span={section_rms_span:.2f}"
                    )
                if len(section_hashes) < 24:
                    raise RuntimeError(
                        f"{label} collapses to {len(section_hashes)}/32 distinct PCM sections"
                    )
                record.update({
                    "nominal_form_seconds": round(nominal_seconds, 3),
                    "live_tempo_drift_seconds": round(drift_seconds, 3),
                    "live_tempo_drift_ratio": round(drift_ratio, 4),
                    "section_rms_min": round(min(section_rms), 3),
                    "section_rms_max": round(max(section_rms), 3),
                    "section_rms_span": round(section_rms_span, 3),
                    "distinct_pcm_sections": len(section_hashes),
                })
            records.append(record)
            full_metrics = (
                f" drift={record['live_tempo_drift_ratio']:+.2%} "
                f"dyn={record['section_rms_span']:.2f}"
                if args.full_form else ""
            )
            print(
                f"[{prefix}] {stage_number:02d} {kind:<5} {label:<18} "
                f"peak={record['peak_int8']:>3} rms={rms:>5.2f} "
                f"silence={silence:.1%}{full_metrics}"
            )

    hashes = {record["sha256"] for record in records}
    if len(hashes) != len(records):
        raise RuntimeError("two cartridge previews produced identical PCM")
    track_gap = np.zeros((SAMPLE_RATE * 3 // 4, 2), dtype=np.int8)
    album_parts = []
    track_offsets = []
    album_cursor = 0
    for index, pcm in enumerate(album_chunks):
        if index:
            album_parts.append(track_gap)
            album_cursor += len(track_gap)
        track_offsets.append(album_cursor)
        album_parts.append(pcm)
        album_cursor += len(pcm)
    album_pcm = np.concatenate(album_parts, axis=0)
    collection = "quintra-music-full" if args.full_form else "quintra-music-preview"
    album_wave = args.out / f"{collection}.wav"
    write_wave(album_wave, album_pcm)
    album = {
        "file": album_wave.name,
        "seconds": round(len(album_pcm) / SAMPLE_RATE, 3),
        "sha256": sha256(album_wave),
    }
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        album_opus = args.out / f"{collection}.opus"
        subprocess.run(
            (ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
             "-i", str(album_wave), "-c:a", "libopus", "-b:a", "96k",
             str(album_opus)),
            check=True,
        )
        album["compact_file"] = album_opus.name
        album["compact_sha256"] = sha256(album_opus)
    cue = args.out / f"{collection}.cue"
    cue_lines = [
        'PERFORMER "Quintra"',
        f'TITLE "{"Complete forms" if args.full_form else "Music preview"}"',
        f'FILE "{album_wave.name}" WAVE',
    ]
    for index, (record, offset) in enumerate(zip(records, track_offsets), 1):
        cue_lines.extend((
            f"  TRACK {index:02d} AUDIO",
            f'    TITLE "{record["name"]} ({record["kind"]})"',
            f"    INDEX 01 {cue_timestamp(offset)}",
        ))
    cue.write_text("\n".join(cue_lines) + "\n")
    album["cue_file"] = cue.name
    manifest = {
        "format": ("Quintra cartridge-authentic complete forms" if args.full_form else
                   "Quintra cartridge-authentic opening+development previews"),
        "mode": "full_form" if args.full_form else "opening_and_development",
        "rom_sha256": sha256(music_test.ROM),
        "sample_rate": SAMPLE_RATE,
        "album": album,
        "records": records,
    }
    if args.full_form:
        manifest["form_sections"] = 32
    else:
        manifest["excerpt_seconds"] = args.seconds
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (args.out / f"{collection}.m3u").write_text(
        "#EXTM3U\n" + "\n".join(record["file"] for record in records) + "\n"
    )
    print(f"[{prefix}] PASS {len(records)} distinct WAV files in {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
