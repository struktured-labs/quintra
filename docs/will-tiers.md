# Will tiers

Controls are unchanged: release A to charge, then tap A to spend all stored
Will on the equipped weapon's empowered attack. B retains its class signature;
A+B retains MP-powered Oath Arts and Spirit Convergence. Talking does not spend Will.

Every run starts with a tier-1 cap. Discovering each of the Titan Glove, Tide Raft,
and Rift Hook adds one tier, up to four. Equipping a different tool does not remove
an unlock. The reward card announces the raised limit. The Pack shows stored/cap,
and the contextual HUD shows a stored-tier digit followed by the next tier's bar.

At SPD 5, successive tiers take 3, 4, 5, and 6 additional seconds of exposed
gameplay: 18 seconds total for tier 4. Charge rate is `(15 + min(SPD, 10)) / 20`
times that baseline. Each SPD point above 5 adds 5% to rate, capped at +25%; lower
SPD slows it down. Inversion uses effective SPD. Shields and Mute pause charging.
Menus pause gameplay. Times are gameplay ticks, not a real-time guarantee under
hardware slowdown. Temporary movement-only Haste does not separately multiply Will.

Higher tiers add modest damage and expand the weapon's coverage. Moonfang and
Queen's Needle gain surrounding lanes; Thunderline and Farstrike gain parallel
piercing lanes; Murderstorm and Moon Tide extend their fans around the hero.
Existing boss burst-hit limits still apply. Allocation failure preserves banked Will.

Suspend saves preserve stored tiers and partial charge. Pre-tier saves migrate
the old 180-point full bar into tier 1, or scale partial progress to the new counter.
