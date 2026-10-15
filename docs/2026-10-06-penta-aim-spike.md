# Penta-style A heading spike

Candidate: `038e50b6bc1eda3b825824469b4270042f28c0f493c426e0c9d3839d1a7161c8`.
Parent: `0d1f3d3c`, archived with symbols in `builds/aim-parent-0d1f3d3c`.

Quintra already has eight-direction fire and non-directional hero artwork.
This spike changes remembered heading, not the sprite atlas or projectile angles.
While holding A without B, a diagonal preserves the preceding cardinal heading
if that heading participates in the diagonal. Releasing both direction buttons
then fires along that heading. A single-axis input turns normally. A diagonal
opposite the old heading uses the existing vertical-priority fallback. Movement,
B and A+B input resolution remain unchanged. No save-layout change or new mode
in the menu. The isolated change is the `previous_facing` block in room.c.

Example: Right → hold A and add Up → release Right and Up while holding A.
Parent fires right, northeast, then north. Candidate fires right, northeast,
then right. This is a proposed interpretation of the recording, not a claim to
have reconstructed its exact controller rules from video.

`test_penta_aim.py` uses an empty-enemy/flat-collision fixture with real joypad
inputs. Forty cases span five heroes and eight cardinal-to-diagonal sequences.
It checks projectile vectors, retained heading, neutral fire, cardinal turns,
and unchanged B/chord/plain-movement heading controls. Parent fails the retained
heading gate. Observation-only replay records its old behavior separately in
the report status. Across the same forty sequences, sampled movement positions
and diagonal projectile velocities match exactly; twenty neutral directions
change as intended. This is not a full performance benchmark.

Existing signature-balance and opening-dynamics tests pass. Native screenshots
inspected; artwork does not turn in either build. ROM layout passes, with 646
bytes free in bank 1. Build took roughly three minutes; replays took seconds.

Candidate ROM and capture report: `builds/penta-aim-038e50b6/`.
Not deployed to itch, SD or live hardware. Needs hands-on feel testing before
treating this interpretation as the final control scheme.
