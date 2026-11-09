# Sequence puzzle final note

Status: **implemented.** Issue #22. The last rune of a sequence puzzle
stays audible before the solved fanfare.

## Rule

Stepping on the final plate still unlocks the room, shakes it, and drops
the tool on that frame. The fanfare does not take channel 1 until 12 frames
later, so the plate's own pitch is heard. A push-block solve has no preceding
note and still starts the fanfare immediately.

## Evidence

`scripts/test_puzzle_note.py` solves a live rune phrase. When the seal drops,
channel 1 is still the rune envelope and stays there for several frames
before the fanfare envelope.
