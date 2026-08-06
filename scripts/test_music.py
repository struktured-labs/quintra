#!/usr/bin/env python3
"""ROM regression: nine stage tracks and nine dedicated boss tracks."""
import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import (
    STAGE_BOSS_ROOM, STAGE_START, dungeon_direction, dungeon_size,
)

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
ROOM_W = 20


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


RS, PL, EN, TM, MUSIC, REQUEST, LARGE, WORLD_W, WORLD_H, CAMERA_X, CAMERA_Y = map(
    addr, ("_run_state", "_player", "_entities", "_room_tilemap",
           "_music_track_id", "_music_stage_number",
           "_procgen_current_room_is_large", "_room_world_width",
           "_room_world_height", "_room_camera_x", "_room_camera_y")
)
MUSIC_ROW = addr("_music_row")
MUSIC_FORM_STEP = addr("_music_form_step")
MUSIC_PATTERN_ROW = addr("_music_pattern_row")
MUSIC_MOTIF = addr("_music_motif")


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def pcm_signature(pb, frames):
    """Small signature of the emulator's actual mixed stereo output."""
    signature = []
    lo, hi = 127, -128
    for _ in range(frames):
        pb.tick()
        samples = pb.sound.ndarray
        if samples.size:
            frame_lo, frame_hi = int(samples.min()), int(samples.max())
            lo, hi = min(lo, frame_lo), max(hi, frame_hi)
            signature.append((frame_lo, frame_hi, int(samples.sum())))
    return tuple(signature), lo, hi


def boot_run():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    assert pb.memory[MUSIC] == 18, "title did not select music number 18"
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(60):
        pb.tick()
    return pb


def runtime_track(stage, boss, keep_emulator=False):
    pb = boot_run()
    desired_room = STAGE_BOSS_ROOM[stage] if boss else (
        1 if stage == 0 else STAGE_START[stage])
    pb.memory[RS + 1] = desired_room - 1
    pb.memory[RS + 11] = stage       # bosses_beaten drives stage identity
    pb.memory[RS + 12] = 0
    pb.memory[RS + 13] = 0
    # Boss-route injection starts at the sanctuary.  Mirror a legitimate
    # completed room-2 objective so the persistent Rift Sigil gate admits
    # the synthetic traversal instead of making music coverage bypass it.
    if boss:
        sigils = pb.memory[RS + 23] | (pb.memory[RS + 24] << 8)
        sigils |= (1 << stage)
        pb.memory[RS + 23] = sigils & 0xFF
        pb.memory[RS + 24] = sigils >> 8
        pb.memory[RS + 27] = 1 << 3
        if dungeon_size(stage) >= 12:
            pb.memory[RS + 27] |= 1 << 7
        if dungeon_size(stage) >= 14:
            pb.memory[RS + 28] |= 1 << 7
        if dungeon_size(stage) >= 20:
            pb.memory[RS + 28] |= 1 << 2
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == 2:
            pb.memory[ep] = pb.memory[ep + 1] = 0
    assert pb.memory[RS + 11] == stage, "stage identity write did not stick"
    if boss:
        pb.memory[RS + 6] = 0xFF      # no backtracking direction
        pb.memory[RS + 17] = 0
        # The boss fixture authors a compact sanctuary threshold after
        # rewriting only the logical counter. Do not carry the live wide
        # foyer's bounds into this synthetic predecessor.
        pb.memory[LARGE] = 0
        pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
        pb.memory[CAMERA_X] = pb.memory[CAMERA_Y] = 0
        pb.memory[0xFF43] = pb.memory[0xFF42] = 0
        source_local = desired_room - 1 - STAGE_START[stage]
        target_local = desired_room - STAGE_START[stage]
        direction = dungeon_direction(source_local, target_local)
        for tx, ty in {
            0: ((9, 0), (10, 0)), 1: ((19, 8), (19, 9)),
            2: ((9, 16), (10, 16)), 3: ((0, 8), (0, 9)),
        }[direction]:
            pb.memory[TM + ty * ROOM_W + tx] = 3
        x, y = {
            0: (72, 0), 1: (144, 60),
            2: (72, 120), 3: (0, 60),
        }[direction]
        put16(pb, PL + 9, x)
        put16(pb, PL + 11, y)
    else:
        pb.memory[RS + 17] = 1        # Riftwild dungeon gate
        pb.memory[RS + 18] = 6
        put16(pb, PL + 9, 72)
        put16(pb, PL + 11, 60)
        pb.memory[TM + 9 * ROOM_W + 10] = 1
        pb.tick()                      # settle synthetic state
        pb.memory[TM + 9 * ROOM_W + 10] = 34  # BGT_PORTAL under feet
    for _ in range(30):
        pb.tick()
        if pb.memory[RS + 1] == desired_room:
            break
    assert pb.memory[RS + 1] == desired_room, (
        f"could not enter stage {stage} {'boss' if boss else 'room'}"
    )
    assert pb.memory[RS + 11] == stage, "transition changed stage identity"
    assert pb.memory[RS + 17] == 0, "transition did not enter a dungeon"
    track = pb.memory[MUSIC]
    assert pb.memory[REQUEST] == stage, (
        f"audio request drifted for stage {stage}: {pb.memory[REQUEST]}"
    )
    if stage == 0 and not boss:
        for i in range(32):
            ep = EN + i * 28
            pb.memory[ep] = pb.memory[ep + 1] = 0
        for _ in range(180):
            pb.tick()
        assert pb.memory[MUSIC_FORM_STEP] >= 1, (
            "gameplay score never advanced into its second arranged section"
        )
        pb.memory[MUSIC_FORM_STEP] = 0
        pb.memory[MUSIC_PATTERN_ROW] = 0
        opening_pcm, opening_lo, opening_hi = pcm_signature(pb, 32)
        pb.memory[MUSIC_FORM_STEP] = 12
        pb.memory[MUSIC_PATTERN_ROW] = 0
        development_pcm, development_lo, development_hi = pcm_signature(pb, 32)
        assert pb.memory[MUSIC_MOTIF] >= 4, (
            "bridge never selected the separately authored E-H score bank"
        )
        assert opening_hi - opening_lo >= 2 and development_hi - development_lo >= 2, (
            "stage score did not reach the emulator's mixed PCM output"
        )
        assert opening_pcm != development_pcm, (
            "development produced the same mixed PCM signature as the opening"
        )
    if keep_emulator:
        return pb, track
    pb.stop(save=False)
    return track


def stage_door_keeps_phrase():
    """A real same-stage doorway must not restart the sequencer at row zero."""
    pb = boot_run()
    for i in range(32):
        ep = EN + i * 28
        pb.memory[ep] = pb.memory[ep + 1] = 0
    # Start well away from the loop boundary. The slide takes enough frames
    # for the row to advance a little, but a mistaken `music_play_stage()`
    # would reset it near zero instead of preserving this phrase position.
    pb.memory[MUSIC_ROW] = 17
    pb.memory[MUSIC_FORM_STEP] = 5
    pb.memory[MUSIC_PATTERN_ROW] = 8
    # The opening room is a real scrolling field. Its east threshold is at
    # the 31x31 perimeter, not the former x=152 viewport seam.
    put16(pb, PL + 9, pb.memory[WORLD_W] - 16)
    put16(pb, PL + 11, 60)
    for _ in range(80):
        pb.tick()
        if pb.memory[RS + 1] == 1:
            break
    assert pb.memory[RS + 1] == 1, "real east door did not enter room 1"
    assert pb.memory[MUSIC] == 0, "same-stage door changed exploration track"
    # 17 remains safely distinct from a reset row (0..2) across the short
    # streamed transition. This also detects an accidental stop/restart.
    assert pb.memory[MUSIC_ROW] >= 17, (
        f"stage phrase restarted across door: row={pb.memory[MUSIC_ROW]}"
    )
    assert pb.memory[MUSIC_FORM_STEP] >= 5, (
        f"stage form restarted across door: section={pb.memory[MUSIC_FORM_STEP]}"
    )
    pb.stop(save=False)


def live_form_frame_count(stage, boss, tempo):
    """Measure a complete live form in hardware VBlanks under encounter load."""
    pb, track = runtime_track(stage, boss, keep_emulator=True)
    try:
        def tick_alive():
            pb.memory[PL + 1] = max(pb.memory[PL + 1], 40)
            pb.memory[PL + 2] = pb.memory[PL + 1]
            pb.memory[PL + 15] = 255
            pb.tick()
            assert pb.memory[MUSIC] == track, "track changed during timing proof"

        # Route injection announces the destination before a large encounter
        # necessarily finishes one-time setup. Drain that work and any VBlank
        # delta before placing the score at its first authored row.
        for _ in range(60):
            tick_alive()
        pb.memory[MUSIC_FORM_STEP] = 0
        pb.memory[MUSIC_PATTERN_ROW] = 0
        pb.memory[MUSIC_ROW] = 0
        for _ in range(120):
            tick_alive()
            if pb.memory[MUSIC_FORM_STEP] == 0 and pb.memory[MUSIC_PATTERN_ROW] == 1:
                break
        else:
            raise AssertionError("score never synchronized to section A row 1")

        frames = 1
        saw_final_quarter = False
        for _ in range(60 * 100):
            tick_alive()
            step = pb.memory[MUSIC_FORM_STEP]
            row = pb.memory[MUSIC_PATTERN_ROW]
            if step >= 24:
                saw_final_quarter = True
            if saw_final_quarter and step == 0 and row == 1:
                break
            frames += 1
        else:
            raise AssertionError("complete score form never wrapped")
    finally:
        pb.stop(save=False)
    expected = tempo * 512
    assert abs(frames - expected) <= 12, (
        f"{'boss' if boss else 'stage'} {stage} music drifted to "
        f"{frames} VBlanks; expected {expected}"
    )
    return frames


def variant_rows(name):
    """Return (melody, bass) source pairs from the compiled-in lookup table.

    GBC audio-register reads are not observable in every PyBoy backend.  The
    ROM traversal above proves each route enters its runtime track; this small
    source contract prevents an otherwise invisible regression where those
    routes use distinct IDs but point back to the same authored phrase.
    """
    text = (ROOT / "src/audio/music_data.c").read_text()
    match = re.search(
        rf"static const music_variant_t {name}\[MUSIC_STAGE_COUNT\] = \{{(.*?)\n\}};",
        text,
        re.S,
    )
    assert match, f"missing {name} table"
    rows = [tuple(field.strip() for field in row.split(","))
            for row in re.findall(r"\{([^{}]+)\}", match.group(1))]
    assert len(rows) == 9 and all(len(row) == 13 for row in rows), (
        f"{name} table changed shape: {rows}"
    )
    return rows


def table_pairs(name):
    return [(row[0], row[1]) for row in variant_rows(name)]


def table_tempos(name):
    return [int(row[2], 0) for row in variant_rows(name)]


def table_swings(name):
    return [int(row[8], 0) for row in variant_rows(name)]


def authored_forms(filename, name):
    text = (ROOT / filename).read_text()
    match = re.search(
        rf"const u8 {name}\[MUSIC_STAGE_COUNT\]\[MUSIC_FORM_SECTIONS\] = \{{(.*?)\n\}};",
        text,
        re.S,
    )
    assert match, f"missing {name}"
    rows = re.findall(r"\{([^{}]+)\}", match.group(1))
    forms = [[int(value) for value in re.findall(r"\b[0-7]\b", row)]
             for row in rows]
    assert len(forms) == 9 and all(len(row) == 32 for row in forms), (
        f"{name} must contain nine authored 32-section forms: {forms}"
    )
    return forms


def note_tracks(source, name):
    match = re.search(
        rf"const u8 {name}\[MUSIC_STAGE_COUNT\]\[(?:64|16)\] = \{{(.*?)\n\}};",
        source,
        re.S,
    )
    assert match, f"missing {name}"
    rows = re.findall(r"\{([^{}]+)\}", match.group(1))
    return [tuple(re.findall(r"\bT_(?:REST|[A-Z0-9]+)\b", row)) for row in rows]


PITCH_CLASS = {
    "C": 0, "CS": 1, "D": 2, "DS": 3, "E": 4, "F": 5,
    "FS": 6, "G": 7, "GS": 8, "A": 9, "AS": 10, "B": 11,
}
STAGE_SCALES = (
    0x0AB5,  # D Dorian
    0x0AD5,  # E Aeolian
    0x06B5,  # A Phrygian
    0x0AD6,  # G Lydian
    0x05AD,  # F Dorian
    0x06B6,  # D harmonic minor
    0x0AD5,  # C Lydian
    0x0B35,  # A harmonic minor
    0x0B6D,  # C octatonic
)
CHARACTER_TONES = (
    {"B"}, {"FS"}, {"AS"}, {"CS", "FS"}, {"DS", "GS", "AS"},
    {"CS", "AS"}, {"FS"}, {"GS"}, {"DS", "FS", "GS"},
)


def opening_melodies(filename):
    source = (ROOT / filename).read_text()
    rows = re.findall(r"const u8 \w*melody\[64\] = \{(.*?)\n\};", source, re.S)
    return [tuple(re.findall(r"\bT_(?:REST|[A-Z0-9]+)\b", row)) for row in rows]


def token_pitch(token):
    if token in ("T_REST", "T_HOLD"):
        return None
    match = re.fullmatch(r"T_([A-G](?:S)?)[356]", token)
    assert match, f"unrecognized score token {token}"
    return PITCH_CLASS[match.group(1)]


def token_midi(token):
    if token in ("T_REST", "T_HOLD"):
        return None
    match = re.fullmatch(r"T_([A-G](?:S)?)([356])", token)
    assert match, f"unrecognized score token {token}"
    return 12 * (int(match.group(2)) + 1) + PITCH_CLASS[match.group(1)]


def melodic_trigrams(notes):
    resolved = []
    previous = "T_REST"
    for note in notes:
        if note == "T_HOLD":
            resolved.append(previous)
        else:
            resolved.append(note)
            previous = note
    return {
        tuple(resolved[index:index + 3])
        for index in range(len(resolved) - 2)
        if "T_REST" not in resolved[index:index + 3]
    }


def rhythmic_sections(notes):
    """Reduce one eight-section score to note/hold/rest articulation."""
    assert len(notes) == 128, f"expected eight 16-row sections, found {len(notes)} rows"
    return tuple(
        tuple(
            "R" if note == "T_REST" else "H" if note == "T_HOLD" else "N"
            for note in notes[start:start + 16]
        )
        for start in range(0, len(notes), 16)
    )


def main():
    stages = [runtime_track(stage, False) for stage in range(9)]
    bosses = [runtime_track(stage, True) for stage in range(9)]
    stage_phrases = table_pairs("stage_music")
    boss_phrases = table_pairs("boss_music")
    assert stages == list(range(9)), f"stage music numbers drifted: {stages}"
    assert bosses == list(range(9, 18)), f"boss music numbers drifted: {bosses}"
    assert set(stages).isdisjoint(bosses), "boss music reused an exploration id"
    assert len(set(stage_phrases)) == 9, f"stage phrases overlap: {stage_phrases}"
    assert len(set(boss_phrases)) == 9, f"boss phrases overlap: {boss_phrases}"
    source = "\n".join((ROOT / name).read_text() for name in (
        "src/audio/music_stage_score.c", "src/audio/music_boss_score.c"
    ))
    long_melodies = re.findall(r"const u8 \w*melody\[64\]", source)
    long_basses = re.findall(r"const u8 (?:\w*bass|bassline)\[16\]", source)
    assert len(long_melodies) == 18, f"expected 18 long arrangements, found {len(long_melodies)}"
    assert len(long_basses) == 18, f"expected 18 long bass parts, found {len(long_basses)}"
    development = (ROOT / "src/audio/music_development_score.c").read_text()
    assert re.search(r"stage_development_melody\[MUSIC_STAGE_COUNT\]\[64\]", development)
    assert re.search(r"stage_development_bass\[MUSIC_STAGE_COUNT\]\[16\]", development)
    assert re.search(r"boss_development_melody\[MUSIC_STAGE_COUNT\]\[64\]", development)
    assert re.search(r"boss_development_bass\[MUSIC_STAGE_COUNT\]\[16\]", development)
    development_tracks = []
    for name, width in (
        ("stage_development_melody", 64), ("stage_development_bass", 16),
        ("boss_development_melody", 64), ("boss_development_bass", 16),
    ):
        tracks = note_tracks(development, name)
        assert len(tracks) == 9 and all(len(track) == width for track in tracks), (
            f"{name} is not nine fully authored tracks"
        )
        assert len(set(tracks)) == 9, f"{name} reused a development score"
        development_tracks.append(tracks)
    assert set(development_tracks[0]).isdisjoint(development_tracks[2]), (
        "a boss reused an exploration development melody"
    )
    stage_openings = opening_melodies("src/audio/music_stage_score.c")
    boss_openings = opening_melodies("src/audio/music_boss_score.c")
    assert len(stage_openings) == len(boss_openings) == 9
    stage_scores = [
        stage_openings[stage] + development_tracks[0][stage]
        for stage in range(9)
    ]
    boss_scores = [
        boss_openings[stage] + development_tracks[2][stage]
        for stage in range(9)
    ]
    all_rhythms = []
    all_melodic_cells = []
    plain_retrigger = tuple("NNNNNNNNNNNNNNNR")
    for stage in range(9):
        scale = STAGE_SCALES[stage]
        characteristic = {PITCH_CLASS[name] for name in CHARACTER_TONES[stage]}
        for label, score in (
            ("stage", stage_scores[stage]),
            ("boss", boss_scores[stage]),
        ):
            pitches = {pitch for note in score if (pitch := token_pitch(note)) is not None}
            outside = sorted(pitch for pitch in pitches if not scale & (1 << pitch))
            assert not outside, f"{label} {stage} leaves its authored mode: {outside}"
            assert characteristic <= pitches, (
                f"{label} {stage} lost characteristic tones {characteristic - pitches}"
            )
            assert len(pitches) >= 6, f"{label} {stage} pitch language collapsed: {pitches}"
            assert score.count("T_HOLD") >= 6, (
                f"{label} {stage} lost authored note lengths: {score.count('T_HOLD')} ties"
            )
            assert score.count("T_REST") >= 10, (
                f"{label} {stage} lost all breathing room: {score.count('T_REST')} rests"
            )
            rhythms = rhythmic_sections(score)
            assert len(set(rhythms)) >= 4, (
                f"{label} {stage} lacks section-level rhythmic development"
            )
            assert plain_retrigger not in rhythms, (
                f"{label} {stage} regressed to continuous row-by-row retriggering"
            )
            all_rhythms.extend(rhythms)
            all_melodic_cells.append((label, stage, melodic_trigrams(score)))
            for index, note in enumerate(score):
                if note != "T_HOLD":
                    continue
                assert index % 16 and score[index - 1] not in ("T_REST", "T_HOLD"), (
                    f"{label} {stage} has an orphan tie at row {index}"
                )

        # A Colossus must recall its dungeon without copying it. Shared
        # melodic cells provide the leitmotif; an upper bound rejects the old
        # near-identical stage/boss phrases.
        stage_cells = melodic_trigrams(stage_openings[stage])
        boss_cells = melodic_trigrams(boss_openings[stage])
        overlap = len(stage_cells & boss_cells) / min(len(stage_cells), len(boss_cells))
        assert 0.15 <= overlap <= 0.65, (
            f"stage/boss {stage} leitmotif balance is {overlap:.2f}"
        )
    rhythm_profile_count = len(set(all_rhythms))
    max_rhythm_reuse = max(all_rhythms.count(pattern) for pattern in set(all_rhythms))
    assert rhythm_profile_count >= 50, (
        f"rhythmic language collapsed to {rhythm_profile_count}/144 section profiles"
    )
    assert max_rhythm_reuse <= 20, (
        f"one articulation pattern dominates {max_rhythm_reuse}/144 sections"
    )
    max_unrelated_motif = 0.0
    max_unrelated_pair = None
    for left in range(len(all_melodic_cells)):
        left_kind, left_stage, left_cells = all_melodic_cells[left]
        for right in range(left + 1, len(all_melodic_cells)):
            right_kind, right_stage, right_cells = all_melodic_cells[right]
            if left_stage == right_stage and left_kind != right_kind:
                continue  # the matching Colossus deliberately recalls its dungeon
            overlap = len(left_cells & right_cells) / min(
                len(left_cells), len(right_cells)
            )
            if overlap > max_unrelated_motif:
                max_unrelated_motif = overlap
                max_unrelated_pair = (left_kind, left_stage, right_kind, right_stage)
    assert max_unrelated_motif <= 0.35, (
        f"unrelated tracks {max_unrelated_pair} share {max_unrelated_motif:.1%} "
        "of the smaller melodic vocabulary"
    )
    stage_forms = authored_forms("src/audio/music_development_score.c", "stage_forms")
    boss_forms = authored_forms("src/audio/music_development_score.c", "boss_forms")
    for label, forms in (("stage", stage_forms), ("boss", boss_forms)):
        assert len({tuple(form) for form in forms}) == 9, f"{label} forms overlap"
        assert all(set(form) == set(range(8)) for form in forms), (
            f"every {label} form must develop all eight authored sections"
        )
        assert all(form[:16] != form[16:] for form in forms), (
            f"a {label} form merely repeats its first half"
        )
    for label, forms, scores in (
        ("stage", stage_forms, stage_scores),
        ("boss", boss_forms, boss_scores),
    ):
        for stage, (form, score) in enumerate(zip(forms, scores)):
            ending = score[form[-1] * 16:(form[-1] + 1) * 16]
            restart = score[form[0] * 16:(form[0] + 1) * 16]
            final_pitch = next(
                token_midi(note) for note in reversed(ending)
                if token_midi(note) is not None
            )
            restart_pitch = next(
                token_midi(note) for note in restart
                if token_midi(note) is not None
            )
            seam = restart_pitch - final_pitch
            assert abs(seam) <= 12, (
                f"{label} {stage} has an exposed {seam:+d}-semitone loop seam"
            )
            if ending[-1] != "T_REST":
                assert seam in (-12, 0, 12), (
                    f"{label} {stage} lacks a cadence rest or seamless unison/octave return"
                )
    stage_tempos = table_tempos("stage_music")
    boss_tempos = table_tempos("boss_music")
    stage_seconds = [tempo * 512 / 60 for tempo in stage_tempos]
    boss_seconds = [tempo * 512 / 60 for tempo in boss_tempos]
    assert all(59.5 <= seconds <= 90 for seconds in stage_seconds), stage_seconds
    assert all(35 <= seconds <= 60 for seconds in boss_seconds), boss_seconds
    stage_swings = table_swings("stage_music")
    boss_swings = table_swings("boss_music")
    assert stage_swings == [0, 1, 0, 1, 2, 1, 0, 1, 2], stage_swings
    assert boss_swings == [0, 1, 0, 1, 2, 1, 0, 1, 1], boss_swings
    engine = (ROOT / "src/audio/music.c").read_text()
    data_engine = (ROOT / "src/audio/music_data.c").read_text()
    assert "play_harmony(boss)" in engine and "play_percussion(boss)" in engine
    assert "sfx_music_ch1_clear()" in engine and "sfx_music_ch4_clear()" in engine
    stage_rows = variant_rows("stage_music")
    boss_rows = variant_rows("boss_music")
    assert tuple(int(row[9], 0) for row in stage_rows) == STAGE_SCALES
    assert tuple(int(row[9], 0) for row in boss_rows) == STAGE_SCALES
    stage_grooves = tuple((int(row[11], 0), int(row[12], 0)) for row in stage_rows)
    boss_grooves = tuple((int(row[11], 0), int(row[12], 0)) for row in boss_rows)
    assert len(set(stage_grooves)) == 9, f"stage drum grooves overlap: {stage_grooves}"
    assert len(set(boss_grooves)) == 9, f"boss drum grooves overlap: {boss_grooves}"
    assert "wave_shape[MUSIC_WAVE_COUNT][16]" in data_engine
    assert "music_read_variant" in data_engine and "BANKED" in data_engine
    assert "music_prepare_harmony" in data_engine and "scale_has(scale" in data_engine
    assert "active_harmony" in engine
    assert "note_code == T_HOLD" in engine and "row_frames" in engine
    stage_door_keeps_phrase()
    ember_form_frames = live_form_frame_count(2, False, stage_tempos[2])
    void_form_frames = live_form_frame_count(8, True, boss_tempos[8])
    print(f"[music] PASS stages={stages}, bosses={bosses}, "
          f"stage_forms={min(stage_seconds):.1f}-{max(stage_seconds):.1f}s, "
          f"boss_forms={min(boss_seconds):.1f}-{max(boss_seconds):.1f}s, "
          f"8 sections/track, rhythm_profiles={rhythm_profile_count}/144 "
          f"(max_reuse={max_rhythm_reuse}), 9 modes, 18 grooves, "
          f"unrelated_motif_max={max_unrelated_motif:.1%}, "
          "18 voice-led cadences, valid_ties+swing, leitmotif-linked bosses, "
          f"vblank_locked=ember:{ember_form_frames}f/void:{void_form_frames}f, "
          "mixed_PCM=opening+development, title=18")


if __name__ == "__main__":
    main()
