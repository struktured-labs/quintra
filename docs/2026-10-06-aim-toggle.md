# Live aim comparison toggle

ROM `c4490bad91a71e3b0e7c62ee414d6807f033a4ada272aad4985640de09b87f00`.

START → SELECT opens AIM TEST. A switches CLASSIC / PENTA HOLD. B or START
resumes the same room. SELECT continues to Gear, Status, Combat Help, then Pack.
The mode persists across menu/room changes for this session and resets to Penta
Hold on ROM restart. No SRAM-format change. The menu shows the right → up-right
→ neutral-fire comparison and its expected result for the selected mode.

`test_aim_toggle.py` switches Classic/Penta/Classic through actual menu input
and verifies different neutral projectile vectors within one run, no resource
cost, resume and page cycling. Existing 40-case aim test, inventory action-tip,
gear layout, Warden/gear gate and cold-resume palette tests pass. The Warden
fixture needed to wait for Pack painting before sending the new extra SELECT
edge; no cartridge input behavior was changed to satisfy it. Native mode pages
were inspected. Build layout passes with 623 bytes free in bank 1.

ROM and screenshots: `builds/aim-toggle-c4490bad/`.
Not reloaded on rivalmage: user confirmation requested while building, current
run left alone. No SD or itch deployment.

Follow-up: Sara's directional artwork is an essential visual distinction.
Quintra still uses non-directional hero poses; this toggle compares only the
retained-heading input spike. Front/back/side artwork remains unimplemented.
