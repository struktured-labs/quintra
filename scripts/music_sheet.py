#!/usr/bin/env python3
"""Validate a Quintra two-voice composition sheet and print C-ready tables.

This deliberately does not write game source.  It gives the composer a small,
repeatable check before a reviewed import into src/audio/music.c.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

SECTION_NAMES = {"TRACK", "DESTINATION", "TEMPO", "MELODY", "BASS"}
NOTE_RE = re.compile(r"^([A-G])(?:#|S)?([0-8])$")


@dataclass(frozen=True)
class Sheet:
    track: str
    destination: str
    tempo: int
    melody: list[str]
    bass: list[str]


def midi(note: str) -> int:
    """Return a MIDI note number.  The caller has already rejected rests."""
    match = NOTE_RE.fullmatch(note)
    if not match:
        raise ValueError(f"invalid note {note!r}; use C5, F#5 (or FS5), or -")
    letter, octave = match.groups()
    semitone = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[letter]
    if "#" in note or "S" in note:
        semitone += 1
    return (int(octave) + 1) * 12 + semitone


def normalize_note(token: str) -> str:
    token = token.strip().upper().replace("♯", "#")
    if token == "-":
        return token
    match = NOTE_RE.fullmatch(token)
    if not match:
        raise ValueError(f"invalid note {token!r}; use C5, F#5 (or FS5), or -")
    letter, octave = match.groups()
    return f"{letter}{'#' if '#' in token or 'S' in token else ''}{octave}"


def split_rows(text: str, wanted: int, label: str) -> list[str]:
    tokens: list[str] = []
    for token in text.replace("|", " ").split():
        # Numbered worksheet rows are labels rather than notes.
        if re.fullmatch(r"\d{1,2}", token):
            continue
        tokens.append(normalize_note(token))
    if len(tokens) != wanted:
        raise ValueError(f"{label} needs exactly {wanted} notes/rests; found {len(tokens)}")
    return tokens


def parse_sheet(text: str) -> Sheet:
    parts: dict[str, list[str] | str] = {}
    active: str | None = None
    for number, raw in enumerate(text.splitlines(), 1):
        # A sharp belongs to a note (F#5).  Only a whitespace-prefixed #
        # starts an inline comment; a whole-line # remains a comment too.
        line = re.split(r"\s+#(?=\s|$)", raw, maxsplit=1)[0].strip()
        if not line:
            continue
        match = re.match(r"^([A-Za-z]+)\s*:\s*(.*)$", line)
        if match:
            key, value = match.group(1).upper(), match.group(2)
            if key in SECTION_NAMES:
                if key in parts:
                    raise ValueError(f"line {number}: {key} appears more than once")
                parts[key] = [] if key in {"MELODY", "BASS"} else value.strip()
                active = key if key in {"MELODY", "BASS"} else None
                continue
        if active is None:
            raise ValueError(f"line {number}: expected a TRACK, DESTINATION, TEMPO, MELODY, or BASS field")
        assert isinstance(parts[active], list)
        parts[active].append(line)

    missing = [field for field in SECTION_NAMES if field not in parts]
    if missing:
        raise ValueError("missing field(s): " + ", ".join(sorted(missing)))
    try:
        tempo = int(str(parts["TEMPO"]))
    except ValueError as exc:
        raise ValueError("TEMPO must be a whole number of frames per row") from exc
    if not 2 <= tempo <= 16:
        raise ValueError("TEMPO must be 2–16 frames per row for the current sequencer")
    track, destination = str(parts["TRACK"]), str(parts["DESTINATION"])
    if not track or not destination:
        raise ValueError("TRACK and DESTINATION must not be empty")
    melody = split_rows(" ".join(parts["MELODY"]), 32, "MELODY")
    bass = split_rows(" ".join(parts["BASS"]), 8, "BASS")
    for note in melody:
        if note != "-" and not (midi("C5") <= midi(note) <= midi("E6")):
            raise ValueError(f"melody note {note} is outside C5–E6")
    for note in bass:
        if note != "-" and not (midi("C3") <= midi(note) <= midi("A3")):
            raise ValueError(f"bass note {note} is outside C3–A3")
    return Sheet(track, destination, tempo, melody, bass)


def gb_frequency(note: str) -> int:
    if note == "-":
        return 0
    hertz = 440.0 * 2 ** ((midi(note) - 69) / 12)
    return round(2048 - 131072 / hertz)


def c_symbol(track: str) -> str:
    symbol = re.sub(r"[^a-z0-9]+", "_", track.lower()).strip("_")
    if not symbol:
        symbol = "composed"
    if symbol[0].isdigit():
        symbol = "track_" + symbol
    return symbol[:40]


def format_table(name: str, notes: list[str], width: int) -> str:
    rows = []
    for start in range(0, len(notes), width):
        entries = [f"{gb_frequency(note):4d} /* {note:3} */" for note in notes[start:start + width]]
        rows.append("    " + ", ".join(entries) + ",")
    return f"static const u16 {name}[{len(notes)}] = {{\n" + "\n".join(rows) + "\n};"


def render(sheet: Sheet) -> str:
    symbol = c_symbol(sheet.track)
    seconds = sheet.tempo * len(sheet.melody) / 60
    return "\n".join((
        f"{sheet.track} → {sheet.destination}",
        f"tempo {sheet.tempo} frames/row; nominal loop {seconds:.1f}s",
        "",
        format_table(f"{symbol}_melody", sheet.melody, 4),
        "",
        format_table(f"{symbol}_bass", sheet.bass, 4),
        "",
        "Install by adding these arrays and one music_variant_t entry in the reviewed track table.",
    ))


def self_test() -> None:
    sheet = parse_sheet("""TRACK: Test Theme
DESTINATION: title
TEMPO: 8
MELODY:
01 C5 02 D5 03 - 04 F#5 05 G5 06 A5 07 B5 08 C6
09 C5 10 D5 11 - 12 F#5 13 G5 14 A5 15 B5 16 C6
17 C5 18 D5 19 - 20 F#5 21 G5 22 A5 23 B5 24 C6
25 C5 26 D5 27 - 28 F#5 29 G5 30 A5 31 B5 32 C6
BASS:
01 C3 02 G3 03 A3 04 - 05 C3 06 G3 07 A3 08 -
""")
    assert gb_frequency("C5") == 1798
    assert gb_frequency("D5") == 1825
    assert sheet.melody[3] == "F#5"
    assert "1798 /* C5" in render(sheet)
    try:
        parse_sheet("TRACK: Bad\nDESTINATION: title\nTEMPO: 8\nMELODY: C5\nBASS: C3")
    except ValueError:
        pass
    else:
        raise AssertionError("short rows were accepted")
    print("[music-sheet] PASS parser, ranges, and Game Boy frequency conversion")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sheet", nargs="?", type=Path, help="plain-text composition sheet")
    parser.add_argument("--self-test", action="store_true", help="run parser/conversion checks")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.sheet is None:
        parser.error("a composition sheet is required (or use --self-test)")
    try:
        print(render(parse_sheet(args.sheet.read_text())))
    except (OSError, ValueError) as exc:
        print(f"music-sheet: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
