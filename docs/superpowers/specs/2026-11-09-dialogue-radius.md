# Dialogue reach

Status: **implemented.** Issue #17. Talking requires being close, and
past arm's reach it also requires not facing away.

## Rule

A resident or wayfarer answers A inside a 20-pixel box. Inside 14 pixels
any facing talks, so a counter you are touching still works. Between 14
and 20 pixels, facing away does not talk and A attacks instead. Farther
than 20 pixels, A attacks. The nearest speaker still wins. The overhead
cue uses the same 20-pixel box. Rooms without speakers still skip the check.

## Evidence

`scripts/test_dialogue_radius.py` stands 26 pixels from a wayfarer and
attacks, stands 16 pixels facing away and attacks, then faces the wayfarer
and opens the dialogue.
