# Riftwild clarity and discovery polish

Candidate ROM: `a51e7e78e252d1db98996575835babaa78a27d42975742f96645da12f2c26419`.
Parent: `17da78a8`, archived with linker symbols in `builds/polish-parent-17da78a8`.

- Fixed the second dialogue topic clamp: Bellwater topics 14/15 and sealed
  arches 13 previously became generic vault conversations. The October 4 test
  checked entry into dialogue but not topic identity; strengthened that check.
- Sealed arches distinguish the current Warden-gated destination from other
  sleeping arches. Current destination advice points northeast to its Warden.
- Reed Singer notices raft ownership and the claimed shrine gift. Innate
  Picsean swimming guidance remains intact.
- All four Riftwild vault gifts persist while the player stays in that field.
  Ordinary loot timers remain active. Vault advice explicitly says to take
  gifts before leaving; the existing one-visit rule still prevents farming.

Tests: updated Bellwater discovery/ceremony/revisit/cold-resume test; new
`test_riftwild_polish.py` (dialogue identity, state-dependent rendered pages,
1,000-frame vault wait, ordinary timeout control, collection and no refill);
existing dialogue suite (nine creatures and merchant/residents); cold-resume
palette/atlas regression. All passed. ROM layout check and diff whitespace pass.
Parent fails the new dialogue identity and vault timeout checks.

Fixtures stage progression, position, ownership and claim flags; movement,
field entry, dialogue inputs, pickup behavior and SRAM resume run in the ROM.
Screens inspected at native resolution. No hardware/performance qualification
or deployment claimed. Earlier boss performance gaps remain open.

Evidence: http://100.120.23.124:8919/polish/
