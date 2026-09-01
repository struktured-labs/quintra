# Quintra show-floor runbook

## Pitch

Quintra is a new Game Boy Color roguelike with five monster heroes,
procedural Zelda-like dungeons, and bullet-hell Colossi, running on original
hardware.

## Setup

- Primary: charged Analogue Pocket with the ordinary latest ROM.
- Recovery: the four `QDEMO` ROM/save pairs produced by `make demo-kit`.
- Backup: laptop, known-good wired controller, itch build, and the raw ROM.
- Carry the current ROM hash separately and test the exact display/controller
  chain before doors open.

At a `QDEMO` title, press A for **CONTINUE**. START intentionally creates a
new run and replaces that station's prepared suspend.

## Five-minute path

1. Let the visitor choose a hero and play a fresh Normal run. Wolfkin is the
   quickest recommendation; Easy remains available on the hero screen.
2. If the conversation continues, open `QDEMO 2 BOOMERANG SHOP`, buy the
   Boomerang, and use B during the prepared signature cooldown.
3. Use `QDEMO 3 CRYSTAL BOSS` for the first scrolling Colossus.
4. Use `QDEMO 4 RIFTWILD` only when exploration or the soundtrack comes up.

## Recovery

- Input problem: reconnect before refreshing; use the known-good wired pad if
  the browser remaps the 8BitDo mode.
- Browser problem: switch to the Pocket or mGBA and preserve the visitor's
  time rather than debugging at the table.
- Run ends early: offer another hero or Easy, then use a prepared station if
  they want to see a later system.

## Useful feedback

Ask three things after play:

1. What did you think B did for your hero?
2. What did you think your next goal was?
3. What, if anything, made you want to try another run?

Record the first point of confusion and first exciting moment. Those are more
actionable than a general score.
