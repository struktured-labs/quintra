# Heart pickups and the low-HP pulse

Status: **implemented.** Issues #18 and #20. A collected heart updates the
HUD on the same frame, a refused heart says why, and the white low-HP flash
ends as soon as HP leaves one heart.

## Rules

One heart is `player.hp` of 1 or 2. While HP stays in that band the heart
palette pulses white. The blink counter may wrap for the soft heartbeat
sound; that wrap does not mean the warning is over. Leaving the band, from
a pickup or any other `hud_redraw_hp` call, writes heart-red immediately,
even if a dialog or the pack has borrowed background palette 7.

A heart on the floor is taken when HP is below max and healing is allowed.
The HUD heart tiles update in that call. At full HP the heart stays and the
notice reads `HPFULL`. Hunger still refuses it, shows the existing no-heal
notice, and keeps `H` plus the rooms remaining in the depth slot.

## Evidence

`scripts/test_heart_hud.py` fills a missing half-heart during the white
pulse, refuses a full gauge with `HPFULL`, and refuses a hungry champion
who is short a heart without consuming the pickup.
