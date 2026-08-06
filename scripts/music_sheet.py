#!/usr/bin/env python3
"""Validate a Quintra two-voice composition sheet and print C-ready tables.

This deliberately does not write game source.  It gives the composer a small,
repeatable check before a reviewed import into src/audio/music.c.
Gameplay tracks use eight 16-row ideas (128 melody rows and 32 bass changes)
plus a 32-section A–H form. Compact 32/8 and 64/16 sheets remain accepted for
title, ending, and sketch material.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

SECTION_NAMES = {"TRACK", "DESTINATION", "TEMPO", "MELODY", "BASS", "FORM"}
NOTE_RE = re.compile(r"^([A-G])(?:#|S)?([0-8])$")
DEFAULT_FORM = list("AABACBDABCDBEFEGFGHECFDGACBDGHBA")


@dataclass(frozen=True)
class Sheet:
    track: str
    destination: str
    tempo: int
    melody: list[str]
    bass: list[str]
    form: list[int] | None


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
    if token in ("-", "~"):
        return token
    match = NOTE_RE.fullmatch(token)
    if not match:
        raise ValueError(f"invalid note {token!r}; use C5, F#5 (or FS5), or -")
    letter, octave = match.groups()
    return f"{letter}{'#' if '#' in token or 'S' in token else ''}{octave}"


def split_rows(text: str, label: str) -> list[str]:
    tokens: list[str] = []
    for token in text.replace("|", " ").split():
        # Numbered worksheet rows are labels rather than notes.
        if re.fullmatch(r"\d{1,2}", token):
            continue
        note = normalize_note(token)
        if label == "BASS" and note == "~":
            raise ValueError("bass rows already sustain four melody rows; use a note or -")
        tokens.append(note)
    return tokens


def split_form(text: str) -> list[int]:
    tokens = text.replace("|", " ").upper().split()
    result: list[int] = []
    for token in tokens:
        if token not in set("ABCDEFGH"):
            raise ValueError(f"invalid FORM section {token!r}; use A through H")
        result.append(ord(token) - ord("A"))
    if len(result) != 32:
        raise ValueError(f"FORM needs exactly 32 A/B/C/D sections; found {len(result)}")
    return result


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
                if key in {"MELODY", "BASS", "FORM"}:
                    parts[key] = [value.strip()] if value.strip() else []
                    active = key
                else:
                    parts[key] = value.strip()
                    active = None
                continue
        if active is None:
            raise ValueError(f"line {number}: expected a TRACK, DESTINATION, TEMPO, MELODY, BASS, or FORM field")
        assert isinstance(parts[active], list)
        parts[active].append(line)

    required = SECTION_NAMES - {"FORM"}
    missing = [field for field in required if field not in parts]
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
    melody = split_rows(" ".join(parts["MELODY"]), "MELODY")
    if len(melody) not in (32, 64, 128):
        raise ValueError(f"MELODY needs exactly 32, 64, or 128 notes/rests; found {len(melody)}")
    bass = split_rows(" ".join(parts["BASS"]), "BASS")
    wanted_bass = len(melody) // 4
    if len(bass) != wanted_bass:
        raise ValueError(
            f"BASS needs exactly {wanted_bass} notes/rests for a {len(melody)}-row melody; "
            f"found {len(bass)}"
        )
    for note in melody:
        if note not in ("-", "~") and not (midi("C5") <= midi(note) <= midi("E6")):
            raise ValueError(f"melody note {note} is outside C5–E6")
    for note in bass:
        if note != "-" and not (midi("C3") <= midi(note) <= midi("B3")):
            raise ValueError(f"bass note {note} is outside C3–B3")
    form = split_form(" ".join(parts["FORM"])) if "FORM" in parts else None
    if form is not None and len(melody) != 128:
        raise ValueError("FORM is only valid with a 128-row gameplay score")
    if form is None and len(melody) == 128:
        form = [ord(section) - ord("A") for section in DEFAULT_FORM]
    return Sheet(track, destination, tempo, melody, bass, form)


def gb_frequency(note: str, wave: bool = False) -> int:
    if note == "-":
        return 0
    hertz = 440.0 * 2 ** ((midi(note) - 69) / 12)
    return round(2048 - (65536 if wave else 131072) / hertz)


def c_symbol(track: str) -> str:
    symbol = re.sub(r"[^a-z0-9]+", "_", track.lower()).strip("_")
    if not symbol:
        symbol = "composed"
    if symbol[0].isdigit():
        symbol = "track_" + symbol
    return symbol[:40]


def c_note(note: str) -> str:
    if note == "-":
        return "T_REST"
    if note == "~":
        return "T_HOLD"
    return "T_" + note.replace("#", "S")


def format_table(name: str, notes: list[str], width: int) -> str:
    rows = []
    for start in range(0, len(notes), width):
        entries = [c_note(note) for note in notes[start:start + width]]
        rows.append("    " + ", ".join(entries) + ",")
    return f"const u8 {name}[{len(notes)}] = {{\n" + "\n".join(rows) + "\n};"


def format_form(name: str, form: list[int]) -> str:
    letters = "".join(chr(section + ord("A")) for section in form)
    values = ",".join(str(value) for value in form)
    return f"// FORM {letters}\nconst u8 {name}[MUSIC_FORM_SECTIONS] = {{ {values} }};"


def render(sheet: Sheet) -> str:
    symbol = c_symbol(sheet.track)
    rows = 16 * len(sheet.form) if sheet.form is not None else len(sheet.melody)
    seconds = sheet.tempo * rows / 60
    result = [
        f"{sheet.track} → {sheet.destination}",
        f"tempo {sheet.tempo} frames/row; nominal loop {seconds:.1f}s",
        "",
        format_table(f"{symbol}_melody", sheet.melody[:64], 4),
        "",
        format_table(f"{symbol}_bass", sheet.bass[:16], 4),
    ]
    if sheet.form is not None:
        result.extend(("", format_table(f"{symbol}_development_melody", sheet.melody[64:], 4),
                       "", format_table(f"{symbol}_development_bass", sheet.bass[16:], 4),
                       "", format_form(f"{symbol}_form", sheet.form)))
    result.extend(("", "Install these note-code arrays and form in the reviewed score table."))
    return "\n".join(result)


def self_test() -> None:
    sheet = parse_sheet("""TRACK: Test Theme
DESTINATION: title
TEMPO: 8
MELODY:
01 C5 02 ~ 03 - 04 F#5 05 G5 06 A5 07 B5 08 C6
09 C5 10 D5 11 - 12 F#5 13 G5 14 A5 15 B5 16 C6
17 C5 18 D5 19 - 20 F#5 21 G5 22 A5 23 B5 24 C6
25 C5 26 D5 27 - 28 F#5 29 G5 30 A5 31 B5 32 C6
BASS:
01 C3 02 G3 03 A3 04 - 05 C3 06 G3 07 A3 08 -
""")
    assert gb_frequency("C5") == 1798
    assert gb_frequency("D5") == 1825
    assert gb_frequency("C3", wave=True) == 1547
    assert sheet.melody[3] == "F#5"
    assert sheet.melody[1] == "~"
    assert "T_C5" in render(sheet)
    assert "T_HOLD" in render(sheet)
    assert sheet.form is None
    try:
        parse_sheet("TRACK: Bad\nDESTINATION: title\nTEMPO: 8\nMELODY: C5\nBASS: C3")
    except ValueError:
        pass
    else:
        raise AssertionError("short rows were accepted")
    sketch = parse_sheet("""TRACK: Sketch Test
DESTINATION: stage
TEMPO: 8
MELODY:
""" + " ".join(["C5"] * 64) + "\nBASS:\n" + " ".join(["C3"] * 16))
    assert len(sketch.melody) == 64 and sketch.form is None
    long_sheet = parse_sheet("""TRACK: Long Test
DESTINATION: stage
TEMPO: 8
MELODY:
""" + " ".join(["C5"] * 128) + "\nBASS:\n" + " ".join(["C3"] * 32))
    assert len(long_sheet.melody) == 128 and len(long_sheet.bass) == 32
    assert long_sheet.form is not None and set(long_sheet.form) == set(range(8))
    custom = parse_sheet("""TRACK: Form Test
DESTINATION: stage
TEMPO: 8
MELODY:
""" + " ".join(["C5"] * 128) + "\nBASS:\n" + " ".join(["C3"] * 32) +
        "\nFORM:\n" + " ".join(list("ABCDEFGH" * 4)))
    assert custom.form == list(range(8)) * 4
    assert "0,1,2,3,4,5,6,7" in render(custom)
    assert "68.3s" in render(custom)
    print("[music-sheet] PASS compact/eight-section parser, forms, ranges, and frequencies")


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
